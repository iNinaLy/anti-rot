from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.core.models import ActivityCompletion
from app.modules.news import feeds, service
from app.modules.news.models import NewsArticle
from app.modules.news.schemas import PreferenceIn

NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
STORIES = [
    ("malaysia", "BERNAMA", "Parliament approves funding for rural broadband"),
    ("malaysia", "Malay Mail", "Ringgit strengthens as inflation eases"),
    ("malaysia", "Malaysiakini", "University research grants open this week"),
    ("world", "BBC", "Diplomats begin regional trade negotiations"),
    ("world", "The Guardian", "Global shipping agreement sets new standards"),
    ("world", "BBC", "Voters prepare for an important election"),
    ("discovery", "Malay Mail", "New battery design cuts charging time"),
    ("discovery", "BBC", "Astronomers discover distant planetary system"),
    ("discovery", "The Guardian", "Museum opens interactive history exhibition"),
    ("malaysia", "BERNAMA", "New transport policy expands commuter services"),
    ("world", "The Guardian", "Central banks discuss monetary outlook"),
    ("discovery", "Malay Mail", "Ocean researchers map coral habitats"),
]


def seed(db):
    for index, (category, source, title) in enumerate(STORIES):
        url = f"https://example.com/story/{index}"
        db.add(NewsArticle(url_hash=hashlib.sha256(url.encode()).hexdigest(), url=url, title=title,
            excerpt="Available RSS excerpt.", source=source, category=category, tags="",
            published_at=NOW - timedelta(minutes=index)))
    db.commit()


def test_finite_balanced_daily_briefing_reading_is_private_and_unrewarded(client, owner, other, db, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    seed(db)
    assert client.get("/api/news/briefing").status_code == 401
    briefing = client.get("/api/news/briefing", headers=owner).json()
    assert briefing["total"] == 8
    assert {item["category"] for item in briefing["items"]} == {"malaysia", "world", "discovery"}
    assert len({item["source"] for item in briefing["items"]}) >= 4
    ids = [item["id"] for item in briefing["items"]]
    for item in briefing["items"]:
        assert item["source"] and item["published_at"] and item["url"]
        assert client.put(f"/api/news/stories/{item['id']}/read", headers=owner, json={"read": True}).status_code == 200
    again = client.get("/api/news/briefing", headers=owner).json()
    assert again["caught_up"] and again["read_count"] == 8
    assert [item["id"] for item in again["items"]] == ids
    assert client.get("/api/news/briefing", headers=other).json()["read_count"] == 0
    assert db.scalar(select(func.count()).select_from(ActivityCompletion)) == 0
    assert client.put(f"/api/news/stories/{uuid4()}/read", headers=owner, json={"read": True}).status_code == 404


def test_preferences_filter_crime_and_exclusions_and_do_not_refill_today(client, owner, other, db, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    seed(db)
    db.add(NewsArticle(url_hash="c" * 64, url="https://example.com/crime", title="Police investigate murder case",
        excerpt="", source="BERNAMA", category="malaysia", tags="Crime", published_at=NOW))
    db.commit()
    result = client.get("/api/news/briefing", headers=owner).json()
    assert not any("murder" in item["title"] for item in result["items"])
    first_title = result["items"][0]["title"]
    response = client.put("/api/news/preferences", headers=owner,
        json={"daily_limit": 5, "reduce_crime": True, "excluded_keywords": [first_title]})
    assert response.status_code == 200
    filtered = client.get("/api/news/briefing", headers=owner).json()
    assert len(filtered["items"]) <= 5 and not any(item["title"] == first_title for item in filtered["items"])
    assert {item["id"] for item in filtered["items"]}.issubset({item["id"] for item in result["items"]})
    assert client.get("/api/news/preferences", headers=other).json()["daily_limit"] == 8
    assert client.put("/api/news/preferences", headers=owner, json={"daily_limit": 100}).status_code == 422


def test_title_deduplication_and_malaysia_midnight(db, client, owner, monkeypatch):
    seed(db)
    articles = list(db.scalars(select(NewsArticle).order_by(NewsArticle.published_at.desc())))
    duplicate = NewsArticle(id=uuid4(), url_hash="d" * 64, url="https://example.com/duplicate",
        title=articles[0].title + " today", excerpt="", source="Other publisher", category="malaysia", tags="", published_at=NOW)
    db.add(duplicate); db.commit()
    chosen = service.choose_articles([*articles, duplicate], type('P', (), {
        "daily_limit": 10, "reduce_crime": True, "excluded_keywords": "[]"})())
    assert not (articles[0] in chosen and duplicate in chosen)
    monkeypatch.setattr(service, "utcnow", lambda: datetime(2026, 10, 29, 16, tzinfo=timezone.utc))
    assert client.get("/api/news/briefing", headers=owner).json()["date"] == "2026-10-30"


def test_feed_parser_handles_html_dates_links_and_unsafe_xml():
    raw = b'''<rss version="2.0"><channel><title>News</title><item><title>Useful &amp; interesting update</title>
      <link>https://www.malaymail.com/news/example?utm_source=test&amp;x=1</link>
      <pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate><description>&lt;p&gt;A short excerpt&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;</description>
      </item><item><title>Unsafe</title><link>javascript:alert(1)</link><pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>'''
    parsed = feeds.parse_feed(raw, feeds.FEEDS[1], NOW)
    assert len(parsed) == 1
    assert parsed[0]["url"] == "https://www.malaymail.com/news/example?x=1"
    assert parsed[0]["excerpt"] == "A short excerpt"
    with pytest.raises(Exception):
        feeds.parse_feed(b'<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><rss>&xxe;</rss>', feeds.FEEDS[0], NOW)
    with pytest.raises(Exception):
        feeds.parse_feed(b"not XML", feeds.FEEDS[0], NOW)
    assert feeds.canonical_url("https://www.malaymail.com.evil.test/news", ("malaymail.com",)) is None


def test_feed_failure_is_throttled_and_empty_briefing_can_retry(client, owner, db, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "news_fetch_enabled", True)
    monkeypatch.setattr(feeds, "utcnow", lambda: NOW)
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    calls = []
    def fail(feed, now):
        calls.append(feed.key)
        raise ValueError("unavailable")
    monkeypatch.setattr(feeds, "download", fail)
    first = client.get("/api/news/briefing", headers=owner).json()
    assert first["total"] == 0 and not first["caught_up"] and first["unavailable_sources"]
    client.get("/api/news/briefing", headers=owner)
    assert len(calls) == len(feeds.FEEDS)
    seed(db)
    assert client.get("/api/news/briefing", headers=owner).json()["total"] == 8


def test_old_unreferenced_cache_is_pruned_but_existing_briefing_is_kept(client, owner, db, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    seed(db)
    briefing = client.get("/api/news/briefing", headers=owner).json()
    db.add(NewsArticle(url_hash="e" * 64, url="https://example.com/old", title="Old unselected story",
        excerpt="", source="BBC", category="world", tags="", published_at=NOW - timedelta(days=20)))
    db.commit()
    monkeypatch.setattr(get_settings(), "news_fetch_enabled", True)
    monkeypatch.setattr(feeds, "utcnow", lambda: NOW + timedelta(days=10))
    monkeypatch.setattr(feeds, "download", lambda feed, now: [])
    feeds.refresh_feeds(db)
    assert db.scalar(select(NewsArticle).where(NewsArticle.url_hash == "e" * 64)) is None
    assert db.scalar(select(func.count()).select_from(NewsArticle)) == briefing["total"]

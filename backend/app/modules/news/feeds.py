from calendar import timegm
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import re
from threading import Lock
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from defusedxml.ElementTree import fromstring
import feedparser
import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.modules.news.models import NewsArticle, NewsBriefingItem, NewsFeedState


@dataclass(frozen=True)
class Feed:
    key: str
    source: str
    category: str
    url: str
    domains: tuple[str, ...]


FEEDS = (
    Feed("bernama", "BERNAMA", "malaysia", "https://www.bernama.com/en/rssfeed.php", ("bernama.com",)),
    Feed("mm-malaysia", "Malay Mail", "malaysia", "https://www.malaymail.com/feed/rss/malaysia", ("malaymail.com",)),
    Feed("mm-money", "Malay Mail", "malaysia", "https://www.malaymail.com/feed/rss/money", ("malaymail.com",)),
    Feed("mk-news", "Malaysiakini", "malaysia", "https://www.malaysiakini.com/en/rss/news.rss", ("malaysiakini.com",)),
    Feed("bbc-world", "BBC", "world", "https://feeds.bbci.co.uk/news/world/rss.xml", ("bbc.com", "bbc.co.uk")),
    Feed("guardian-world", "The Guardian", "world", "https://www.theguardian.com/world/rss", ("theguardian.com",)),
    Feed("bbc-science", "BBC", "discovery", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", ("bbc.com", "bbc.co.uk")),
    Feed("mm-tech", "Malay Mail", "discovery", "https://www.malaymail.com/feed/rss/tech-gadgets", ("malaymail.com",)),
)
fetch_lock = Lock()


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(value: str, limit: int) -> str:
    parser = TextOnly()
    parser.feed(unescape(value))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:limit]


def canonical_url(value: str, domains: tuple[str, ...]) -> str | None:
    try:
        url = urlparse(value)
        host = (url.hostname or "").lower()
        if (url.scheme not in ("http", "https") or url.username or url.password or url.port not in (None, 80, 443)
                or not any(host == domain or host.endswith("." + domain) for domain in domains)):
            return None
        query = [(key, value) for key, value in parse_qsl(url.query, keep_blank_values=True)
                 if not key.lower().startswith("utm_") and key.lower() not in ("fbclid", "gclid", "cmpid", "ocid")]
        return urlunparse((url.scheme, url.netloc, url.path, "", urlencode(query), ""))
    except ValueError:
        return None


def parse_feed(raw: bytes, feed: Feed, now: datetime) -> list[dict]:
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Feed too large")
    fromstring(raw)  # Reject DTD/entity attacks before handing bytes to the tolerant RSS parser.
    parsed = feedparser.parse(raw)
    if not parsed.entries:
        raise ValueError("No feed entries")
    items = []
    for entry in parsed.entries[:100]:
        url = canonical_url(entry.get("link", ""), feed.domains)
        title = clean_text(entry.get("title", ""), 500)
        timestamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not url or not title or not timestamp:
            continue
        try:
            published = datetime.fromtimestamp(timegm(timestamp), timezone.utc)
        except (ValueError, OverflowError, OSError):
            continue
        if not now - timedelta(days=3) <= published <= now + timedelta(minutes=15):
            continue
        category = feed.category
        if feed.key == "mm-money" and not re.search(r"\b(malaysia|malaysian|ringgit|bursa|kuala lumpur)\b", f"{title} {entry.get('summary', '')}".casefold()):
            category = "world"
        items.append({"url_hash": hashlib.sha256(url.encode()).hexdigest(), "url": url,
                      "title": title, "excerpt": clean_text(entry.get("summary", ""), 350),
                      "source": feed.source, "category": category,
                      "tags": " ".join(clean_text(tag.get("term", ""), 100) for tag in entry.get("tags", []))[:500],
                      "published_at": published})
    return items


def download(feed: Feed, now: datetime) -> list[dict]:
    with httpx.stream("GET", feed.url, timeout=6, follow_redirects=False,
                      headers={"User-Agent": "Anti-Rot/1.0 (personal non-commercial RSS reader)"}) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 2 * 1024 * 1024:
                raise ValueError("Feed too large")
    return parse_feed(bytes(content), feed, now)


def refresh_feeds(db: Session) -> None:
    if not get_settings().news_fetch_enabled:
        return
    with fetch_lock:
        now = utcnow()
        states = {row.key: row for row in db.scalars(select(NewsFeedState))}
        due = [feed for feed in FEEDS if feed.key not in states or states[feed.key].checked_at < now - timedelta(minutes=30)]
        if not due:
            return
        def fetch(feed):
            try:
                return feed, download(feed, now), True
            except Exception:
                return feed, [], False
        with ThreadPoolExecutor(max_workers=6) as pool:
            for feed, articles, ok in pool.map(fetch, due):
                state = states.get(feed.key) or NewsFeedState(key=feed.key)
                state.checked_at, state.ok = now, ok
                db.add(state)
                for article in articles:
                    if not db.scalar(select(NewsArticle.id).where(NewsArticle.url_hash == article["url_hash"])):
                        db.add(NewsArticle(**article))
                        db.flush()
        db.execute(delete(NewsArticle).where(NewsArticle.published_at < now - timedelta(days=7),
            NewsArticle.id.not_in(select(NewsBriefingItem.article_id))))
        db.commit()

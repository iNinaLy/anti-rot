from collections import Counter
from datetime import timedelta
from difflib import SequenceMatcher
import json
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import utcnow
from app.modules.news.feeds import FEEDS, refresh_feeds
from app.modules.news.models import NewsArticle, NewsBriefing, NewsBriefingItem, NewsFeedState, NewsPreference
from app.modules.news.schemas import PreferenceIn

ZONE = ZoneInfo("Asia/Kuala_Lumpur")
CRIME_WORDS = ("murder", "murdered", "rape", "raped", "robbery", "robber", "kidnapped", "kidnapping",
               "stabbing", "stabbed", "shooting", "gunman", "homicide", "sexual assault", "child abuse",
               "busted", "drug bust", "pembunuhan", "rogol", "rompakan", "culik")


def preferences(db: Session, user_id: UUID) -> NewsPreference:
    preference = db.get(NewsPreference, user_id)
    if not preference:
        preference = NewsPreference(user_id=user_id)
        db.add(preference)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            preference = db.get(NewsPreference, user_id)
    return preference


def preference_dict(preference: NewsPreference) -> dict:
    return {"daily_limit": preference.daily_limit, "reduce_crime": preference.reduce_crime,
            "excluded_keywords": json.loads(preference.excluded_keywords)}


def blocked(article: NewsArticle, preference: NewsPreference) -> bool:
    text = f"{article.title} {article.excerpt} {article.tags}".casefold()
    words = json.loads(preference.excluded_keywords)
    if preference.reduce_crime:
        words += list(CRIME_WORDS)
        if re.search(r"\b(crime|crimes|jenayah)\b", article.tags.casefold()):
            return True
    return any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) for word in words)


def choose_articles(articles: list[NewsArticle], preference: NewsPreference) -> list[NewsArticle]:
    candidates = [article for article in articles if not blocked(article, preference)]
    chosen, sources = [], Counter()
    categories = ("malaysia", "world", "discovery")
    while len(chosen) < preference.daily_limit:
        changed = False
        for category in categories:
            if len(chosen) >= preference.daily_limit:
                break
            def rank(article):
                topical = article.category != "discovery" and re.search(
                    r"\b(parliament|budget|economy|economic|ringgit|inflation|trade|minister|election|government|policy|gdp|interest rate)\b",
                    f"{article.title} {article.excerpt}".casefold())
                return sources[article.source], -int(bool(topical)), -article.published_at.timestamp()
            ordered = sorted(candidates, key=rank)
            for article in ordered:
                if article in chosen or article.category != category or sources[article.source] >= 3:
                    continue
                normalized = re.sub(r"\W+", " ", article.title.casefold()).strip()
                if any(article.url_hash == old.url_hash or SequenceMatcher(None, normalized,
                       re.sub(r"\W+", " ", old.title.casefold()).strip()).ratio() > .8 for old in chosen):
                    continue
                chosen.append(article)
                sources[article.source] += 1
                changed = True
                break
        if not changed:
            break
    return chosen


def get_briefing(db: Session, user_id: UUID) -> dict:
    preference = preferences(db, user_id)
    now = utcnow()
    date = now.astimezone(ZONE).date()
    briefing = db.scalar(select(NewsBriefing).where(NewsBriefing.user_id == user_id, NewsBriefing.local_date == date))
    if not briefing:
        refresh_feeds(db)
        briefing = NewsBriefing(user_id=user_id, local_date=date)
        db.add(briefing)
        try:
            db.flush()
            articles = list(db.scalars(select(NewsArticle).where(NewsArticle.published_at >= now - timedelta(days=3),
                    NewsArticle.published_at <= now + timedelta(minutes=15)).order_by(NewsArticle.published_at.desc(), NewsArticle.id)))
            for index, article in enumerate(choose_articles(articles, preference)):
                db.add(NewsBriefingItem(briefing_id=briefing.id, article_id=article.id, position=index))
            db.commit()
        except IntegrityError:
            db.rollback()
            briefing = db.scalar(select(NewsBriefing).where(NewsBriefing.user_id == user_id, NewsBriefing.local_date == date))
    rows = db.execute(select(NewsBriefingItem, NewsArticle).join(NewsArticle,
        NewsBriefingItem.article_id == NewsArticle.id).where(NewsBriefingItem.briefing_id == briefing.id)
        .order_by(NewsBriefingItem.position)).all()
    if not rows:
        # Failed/empty feeds may recover later; do not freeze an empty briefing for a whole day.
        db.delete(briefing)
        db.commit()
    # Preference changes can hide existing stories; never append another batch today.
    rows = [(item, article) for item, article in rows if not blocked(article, preference)][:preference.daily_limit]
    items = [{"id": article.id, "title": article.title, "excerpt": article.excerpt, "source": article.source,
              "category": article.category, "published_at": article.published_at, "url": article.url,
              "read": item.read} for item, article in rows]
    failed = {state.key for state in db.scalars(select(NewsFeedState).where(NewsFeedState.ok.is_(False)))}
    return {"date": date, "items": items, "total": len(items), "read_count": sum(item["read"] for item in items),
            "caught_up": bool(items) and all(item["read"] for item in items),
            "unavailable_sources": sorted({feed.source for feed in FEEDS if feed.key in failed}),
            "preferences": preference_dict(preference)}


def save_preferences(db: Session, user_id: UUID, data: PreferenceIn) -> dict:
    preference = preferences(db, user_id)
    preference.daily_limit, preference.reduce_crime = data.daily_limit, data.reduce_crime
    preference.excluded_keywords = json.dumps(data.excluded_keywords)
    db.commit()
    return preference_dict(preference)


def mark_read(db: Session, user_id: UUID, article_id: UUID, value: bool) -> dict:
    date = utcnow().astimezone(ZONE).date()
    item = db.scalar(select(NewsBriefingItem).join(NewsBriefing).where(NewsBriefing.user_id == user_id,
        NewsBriefing.local_date == date, NewsBriefingItem.article_id == article_id))
    if not item:
        raise HTTPException(404, "Story not found in your daily briefing")
    item.read = value
    db.commit()
    return {"detail": "Reading progress saved"}

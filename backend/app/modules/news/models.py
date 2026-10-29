from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class NewsArticle(Base):
    __tablename__ = "news_articles"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    excerpt: Mapped[str] = mapped_column(String(600))
    source: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(16), index=True)
    tags: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class NewsFeedState(Base):
    __tablename__ = "news_feed_states"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ok: Mapped[bool] = mapped_column()


class NewsPreference(Base):
    __tablename__ = "news_preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    daily_limit: Mapped[int] = mapped_column(default=8)
    reduce_crime: Mapped[bool] = mapped_column(default=True)
    excluded_keywords: Mapped[str] = mapped_column(Text, default="[]")


class NewsBriefing(Base):
    __tablename__ = "news_briefings"
    __table_args__ = (UniqueConstraint("user_id", "local_date"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    local_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class NewsBriefingItem(Base):
    __tablename__ = "news_briefing_items"
    briefing_id: Mapped[UUID] = mapped_column(ForeignKey("news_briefings.id"), primary_key=True)
    article_id: Mapped[UUID] = mapped_column(ForeignKey("news_articles.id"), primary_key=True)
    position: Mapped[int] = mapped_column()
    read: Mapped[bool] = mapped_column(default=False)

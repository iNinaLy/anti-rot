from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utcnow


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("user_id", "name_key"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(240))


class Deck(Base):
    __tablename__ = "decks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(String(120), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    cards: Mapped[list["Card"]] = relationship(cascade="all, delete-orphan")
    sessions: Mapped[list["ReviewSession"]] = relationship(cascade="all, delete-orphan")


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    deck_id: Mapped[UUID] = mapped_column(ForeignKey("decks.id"), index=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    choices: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    state: Mapped["CardState"] = relationship(cascade="all, delete-orphan", uselist=False)
    images: Mapped[list["CardImage"]] = relationship(cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(cascade="all, delete-orphan")
    session_items: Mapped[list["SessionItem"]] = relationship(cascade="all, delete-orphan")


class CardState(Base):
    __tablename__ = "card_states"
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    interval_days: Mapped[float] = mapped_column(default=0.0)
    ease: Mapped[float] = mapped_column(default=2.5)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    version: Mapped[int] = mapped_column(default=0)
    stability: Mapped[float | None] = mapped_column(nullable=True)
    difficulty: Mapped[float | None] = mapped_column(nullable=True)
    phase: Mapped[int] = mapped_column(default=1, server_default="1")
    learning_step: Mapped[int | None] = mapped_column(nullable=True, default=0)


class ReviewSession(Base):
    __tablename__ = "review_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    deck_id: Mapped[UUID] = mapped_column(ForeignKey("decks.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    items: Mapped[list["SessionItem"]] = relationship(cascade="all, delete-orphan")


class SessionItem(Base):
    __tablename__ = "session_items"
    session_id: Mapped[UUID] = mapped_column(ForeignKey("review_sessions.id"), primary_key=True)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    reviewed: Mapped[bool] = mapped_column(default=False)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("session_id", "card_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), index=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("review_sessions.id"))
    rating: Mapped[str] = mapped_column(String(10))
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    prev_interval: Mapped[float] = mapped_column()
    new_interval: Mapped[float] = mapped_column()
    scheduler: Mapped[str] = mapped_column(String(16), default="fsrs6", server_default="sm2")


class CardImage(Base):
    __tablename__ = "card_images"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id"), index=True)
    side: Mapped[str] = mapped_column(String(5))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)

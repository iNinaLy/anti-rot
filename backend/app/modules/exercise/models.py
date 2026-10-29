from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class ExercisePlan(Base):
    __tablename__ = "exercise_plans"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Nourish Move Love")
    total_days: Mapped[int] = mapped_column(default=30)
    playlist_url: Mapped[str] = mapped_column(String(2048), default="https://www.youtube.com/playlist?list=PLpa0d6IJAhbgN8nyV8BK-GqN_A8CXgu9c")
    workout_links: Mapped[list[str]] = mapped_column(JSON, default=list)
    current_day: Mapped[int] = mapped_column(default=1)
    weekdays: Mapped[str] = mapped_column(String(13), default="1,4,6")
    reminder_time: Mapped[str] = mapped_column(String(5), default="20:00")
    reminders: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=0)


class ExerciseCompletion(Base):
    __tablename__ = "exercise_completions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    day: Mapped[int | None] = mapped_column(nullable=True)
    local_date: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True)
    subscription: Mapped[str] = mapped_column(Text)
    last_sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)

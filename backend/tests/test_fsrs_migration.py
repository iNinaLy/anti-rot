from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fsrs import Card, Rating, Scheduler
import pytest
import sqlalchemy as sa

from app.config import get_settings


def test_migration_replays_history_without_rescheduling_or_losing_logs(tmp_path, monkeypatch):
    settings = get_settings()
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "0001")
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    metadata.reflect(engine)
    tables = metadata.tables
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    user, deck, card_id, new_card_id = [uuid4().hex for _ in range(4)]
    history = [(now - timedelta(days=12), "easy", Rating.Easy),
               (now - timedelta(days=3), "good", Rating.Good)]
    due = now + timedelta(days=8)
    with engine.begin() as conn:
        conn.execute(tables["users"].insert(), {"id": user, "email": "migration@example.com",
            "password_hash": "unused", "created_at": now})
        conn.execute(tables["decks"].insert(), {"id": deck, "user_id": user,
            "name": "Existing deck", "description": "", "created_at": now})
        for cid in (card_id, new_card_id):
            conn.execute(tables["cards"].insert(), {"id": cid, "deck_id": deck,
                "front": "Q", "back": "A", "created_at": now - timedelta(days=15)})
            conn.execute(tables["card_states"].insert(), {"card_id": cid, "due_at": due,
                "interval_days": 11., "ease": 2.6, "reps": 2, "lapses": 0,
                "last_reviewed_at": history[-1][0] if cid == card_id else None, "version": 2})
        for when, rating, _ in history:
            session = uuid4().hex
            conn.execute(tables["review_sessions"].insert(), {"id": session,
                "user_id": user, "deck_id": deck, "created_at": when, "completed_at": when})
            conn.execute(tables["reviews"].insert(), {"id": uuid4().hex, "card_id": card_id,
                "session_id": session, "rating": rating, "reviewed_at": when,
                "prev_interval": 1., "new_interval": 11.})
    command.upgrade(config, "head")
    metadata = sa.MetaData()
    metadata.reflect(engine)
    states, reviews = metadata.tables["card_states"], metadata.tables["reviews"]
    expected, scheduler = Card(card_id=0), Scheduler(enable_fuzzing=False)
    for when, _, rating in history:
        expected, _ = scheduler.review_card(expected, rating, review_datetime=when)
    with engine.connect() as conn:
        migrated = conn.execute(sa.select(states).where(states.c.card_id == card_id)).mappings().one()
        assert migrated["stability"] == pytest.approx(expected.stability)
        assert migrated["difficulty"] == pytest.approx(expected.difficulty)
        assert (migrated["phase"], migrated["learning_step"]) == (expected.state, expected.step)
        assert migrated["due_at"].replace(tzinfo=timezone.utc) == due
        assert migrated["version"] == 2 and migrated["ease"] == 2.6
        assert conn.scalar(sa.select(sa.func.count()).select_from(reviews)) == 2
        assert conn.scalars(sa.select(reviews.c.scheduler)).all() == ["sm2", "sm2"]
        fresh = conn.execute(sa.select(states).where(states.c.card_id == new_card_id)).mappings().one()
        assert fresh["stability"] is None and fresh["learning_step"] == 0
    command.check(config)
    command.downgrade(config, "0001")
    command.upgrade(config, "head")
    engine.dispose()

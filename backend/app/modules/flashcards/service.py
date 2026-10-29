import csv
import io
from dataclasses import asdict
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import utcnow
from app.config import get_settings
from app.media import MediaStore
from app.modules.core.models import ActivityCompletion
from app.modules.flashcards.models import (Card, CardImage, CardState, Deck, Review,
                                           ReviewSession, SessionItem)
from app.modules.flashcards.scheduler import Scheduler, SchedulingState
from app.modules.flashcards.schemas import ReviewIn
from app.modules.flashcards.fsrs_scheduler import FSRS

scheduler: Scheduler = FSRS(get_settings().fsrs_desired_retention)


def owned_deck(db: Session, user_id: UUID, deck_id: UUID) -> Deck:
    deck = db.scalar(select(Deck).where(Deck.id == deck_id, Deck.user_id == user_id))
    if not deck:
        raise HTTPException(404, "Deck not found")
    return deck


def owned_card(db: Session, user_id: UUID, card_id: UUID) -> Card:
    card = db.scalar(select(Card).join(Deck).where(Card.id == card_id, Deck.user_id == user_id))
    if not card:
        raise HTTPException(404, "Card not found")
    return card


def deck_summary(db: Session, deck: Deck) -> dict:
    tomorrow = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return {"id": deck.id, "name": deck.name, "description": deck.description,
            "subject": deck.subject,
            "created_at": deck.created_at,
            "card_count": db.scalar(select(func.count()).select_from(Card).where(Card.deck_id == deck.id)),
            "ready_count": db.scalar(select(func.count()).select_from(Card).join(CardState).where(
                Card.deck_id == deck.id, CardState.due_at <= utcnow())),
            "due_count": db.scalar(select(func.count()).select_from(Card).join(CardState).where(
                Card.deck_id == deck.id, CardState.due_at < tomorrow))}


def remove_unreferenced(db: Session, store: MediaStore, hashes: set[str]) -> None:
    for file_hash in hashes:
        if not db.scalar(select(func.count()).select_from(CardImage).where(CardImage.file_hash == file_hash)):
            store.delete(file_hash)


def import_csv(db: Session, deck_id: UUID, raw: bytes) -> dict:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        if reader.fieldnames is None or not {"front", "back"}.issubset(reader.fieldnames):
            raise HTTPException(422, "CSV must have front,back headers")
        imported, skipped, errors = 0, 0, []
        for number, row in enumerate(reader, 2):
            front, back = row.get("front"), row.get("back")
            if (None in row or front is None or back is None or not front.strip() or not back.strip()
                    or len(front) > 20000 or len(back) > 20000):
                skipped += 1
                if len(errors) < 50:
                    errors.append(f"Row {number}: missing, empty or oversized front/back")
                continue
            db.add(Card(deck_id=deck_id, front=front, back=back, state=CardState()))
            imported += 1
        db.commit()
        return {"imported": imported, "skipped": skipped, "errors": errors}
    except (UnicodeDecodeError, csv.Error):
        db.rollback()
        raise HTTPException(422, "Upload a valid UTF-8 CSV file")


def submit_review(db: Session, user_id: UUID, data: ReviewIn) -> dict:
    card = owned_card(db, user_id, data.card_id)
    existing = db.get(Review, data.id)
    if existing:
        if (existing.card_id, existing.session_id, existing.rating) != (data.card_id, data.session_id, data.rating):
            raise HTTPException(409, "Review ID was already used for a different review")
        return {"id": existing.id, "duplicate": True}
    session = db.scalar(select(ReviewSession).where(
        ReviewSession.id == data.session_id, ReviewSession.user_id == user_id,
        ReviewSession.deck_id == card.deck_id))
    item = db.get(SessionItem, (data.session_id, card.id))
    if not session or not item or item.reviewed or session.completed_at:
        raise HTTPException(409, "Card is not pending in this session")
    state = card.state
    if data.version != state.version:
        raise HTTPException(409, "Card changed on another device; discard this review and reload")
    now = utcnow()
    if data.reviewed_at > now + timedelta(minutes=5) or data.reviewed_at < session.created_at - timedelta(minutes=5):
        raise HTTPException(422, "Review time is outside this session")
    if state.last_reviewed_at and data.reviewed_at < state.last_reviewed_at:
        raise HTTPException(409, "Review predates the last accepted review")
    old = SchedulingState(**{key: getattr(state, key) for key in SchedulingState.__dataclass_fields__})
    updated = scheduler.next_state(old, data.rating, data.reviewed_at)
    result = db.execute(update(CardState).where(CardState.card_id == card.id,
        CardState.version == data.version).values(**asdict(updated), version=data.version + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Card changed on another device")
    db.add(Review(id=data.id, card_id=card.id, session_id=session.id, rating=data.rating,
                  reviewed_at=data.reviewed_at, prev_interval=old.interval_days,
                  new_interval=updated.interval_days))
    item.reviewed = True
    db.commit()
    return {"id": data.id, "duplicate": False}


def finish_session(db: Session, user_id: UUID, session_id: UUID) -> dict:
    session = db.scalar(select(ReviewSession).where(
        ReviewSession.id == session_id, ReviewSession.user_id == user_id))
    if not session:
        raise HTTPException(404, "Session not found")
    if session.completed_at:
        return {"detail": "Session completed"}
    if not session.items or not all(item.reviewed for item in session.items):
        raise HTTPException(409, "Review every card before completing the session")
    result = db.execute(update(ReviewSession).where(ReviewSession.id == session_id,
        ReviewSession.completed_at.is_(None)).values(completed_at=utcnow()))
    if result.rowcount == 1:
        db.add(ActivityCompletion(user_id=user_id, activity_type="flashcards", activity_ref=session.id,
                                  points=len(session.items)))
    db.commit()
    return {"detail": "Session completed"}

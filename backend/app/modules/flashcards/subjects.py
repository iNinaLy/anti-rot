from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.flashcards.models import Deck, Subject

DEFAULT_SUBJECTS = (
    "ITT585 – Network Infrastructure Security",
    "ITT610 – Network Security / Security Analysis",
    "ICT652 – Ethical, Social and Professional Issues in ICT",
    "ITT640 – Wireless Networks",
    "ITT593 – Introduction to Digital Forensics",
)


def list_subjects(db: Session, user_id: UUID) -> list[str]:
    # Include existing deck labels so older custom subjects stay selectable.
    names = [*DEFAULT_SUBJECTS,
             *db.scalars(select(Subject.name).where(Subject.user_id == user_id).order_by(Subject.name)),
             *db.scalars(select(Deck.subject).where(Deck.user_id == user_id).order_by(Deck.created_at))]
    unique = {}
    for name in names:
        if name.strip():
            unique.setdefault(name.strip().casefold(), name.strip())
    return list(unique.values())


def add_subject(db: Session, user_id: UUID, name: str) -> str:
    key = name.casefold()
    existing = next((item for item in list_subjects(db, user_id) if item.casefold() == key), None)
    # A subject already used on a deck is still saved in the independent catalog.
    if existing in DEFAULT_SUBJECTS:
        return existing
    saved = db.scalar(select(Subject).where(Subject.user_id == user_id, Subject.name_key == key))
    if saved:
        return saved.name
    subject = Subject(user_id=user_id, name=existing or name, name_key=key)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(Subject).where(Subject.user_id == user_id, Subject.name_key == key)).name
    return subject.name

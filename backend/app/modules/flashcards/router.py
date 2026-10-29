from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.media import MediaStore, get_media_store, normalize_image
from app.modules.core.models import User
from app.modules.core.schemas import Message
from app.modules.core.service import current_user
from app.modules.flashcards.models import Card, CardImage, CardState, Deck, ReviewSession, SessionItem
from app.modules.flashcards.schemas import (CardIn, CardOut, DeckIn, DeckOut, ImageOut,
                                            ImportOut, ReviewIn, ReviewOut, SessionOut, SubjectIn)
from app.modules.flashcards.subjects import add_subject, list_subjects
from app.modules.flashcards.service import (deck_summary, finish_session, import_csv, owned_card,
                                            owned_deck, remove_unreferenced, submit_review)

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get("/subjects", response_model=list[str])
def subjects(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[str]:
    return list_subjects(db, user.id)


@router.post("/subjects", response_model=SubjectIn, status_code=201)
def create_subject(data: SubjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"name": add_subject(db, user.id, data.name)}


@router.get("/decks", response_model=list[DeckOut])
def decks(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [deck_summary(db, deck) for deck in db.scalars(
        select(Deck).where(Deck.user_id == user.id).order_by(Deck.created_at))]


@router.post("/decks", response_model=DeckOut, status_code=201)
def create_deck(data: DeckIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    deck = Deck(user_id=user.id, **data.model_dump())
    db.add(deck)
    db.commit()
    return deck_summary(db, deck)


@router.get("/decks/{deck_id}", response_model=DeckOut)
def get_deck(deck_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return deck_summary(db, owned_deck(db, user.id, deck_id))


@router.put("/decks/{deck_id}", response_model=DeckOut)
def edit_deck(deck_id: UUID, data: DeckIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    deck = owned_deck(db, user.id, deck_id)
    deck.name, deck.description, deck.subject = data.name, data.description, data.subject
    db.commit()
    return deck_summary(db, deck)


@router.delete("/decks/{deck_id}", response_model=Message)
def delete_deck(deck_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db),
                store: MediaStore = Depends(get_media_store)) -> dict:
    deck = owned_deck(db, user.id, deck_id)
    hashes = {image.file_hash for card in deck.cards for image in card.images}
    db.delete(deck)
    db.commit()
    remove_unreferenced(db, store, hashes)
    return {"detail": "Deck deleted"}


@router.get("/decks/{deck_id}/cards", response_model=list[CardOut])
def cards(deck_id: UUID, due: bool = False, limit: int = Query(1000, ge=1, le=1000),
          offset: int = Query(0, ge=0), user: User = Depends(current_user),
          db: Session = Depends(get_db)) -> list[Card]:
    owned_deck(db, user.id, deck_id)
    query = select(Card).join(CardState).where(Card.deck_id == deck_id)
    if due:
        query = query.where(CardState.due_at <= utcnow())
    return list(db.scalars(query.order_by(CardState.due_at, Card.id).offset(offset).limit(limit)))


@router.post("/decks/{deck_id}/cards", response_model=CardOut, status_code=201)
def create_card(deck_id: UUID, data: CardIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> Card:
    owned_deck(db, user.id, deck_id)
    if not data.front.strip() or not data.back.strip():
        raise HTTPException(422, "Add text to both sides before attaching images")
    card = Card(deck_id=deck_id, **data.model_dump(), state=CardState())
    db.add(card)
    db.commit()
    return card


@router.get("/cards/{card_id}", response_model=CardOut)
def get_card(card_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Card:
    return owned_card(db, user.id, card_id)


@router.put("/cards/{card_id}", response_model=CardOut)
def edit_card(card_id: UUID, data: CardIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> Card:
    card = owned_card(db, user.id, card_id)
    for side in ("front", "back"):
        if not getattr(data, side).strip() and not any(image.side == side for image in card.images):
            raise HTTPException(422, "Each side needs text or an image")
    card.front, card.back, card.tags, card.choices = data.front, data.back, data.tags, data.choices
    db.commit()
    return card


@router.delete("/cards/{card_id}", response_model=Message)
def delete_card(card_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db),
                store: MediaStore = Depends(get_media_store)) -> dict:
    card = owned_card(db, user.id, card_id)
    hashes = {image.file_hash for image in card.images}
    db.delete(card)
    db.commit()
    remove_unreferenced(db, store, hashes)
    return {"detail": "Card deleted"}


@router.post("/decks/{deck_id}/import", response_model=ImportOut)
def upload_csv(deck_id: UUID, file: UploadFile = File(...), user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> dict:
    owned_deck(db, user.id, deck_id)
    data = file.file.read(get_settings().max_csv_bytes + 1)
    if len(data) > get_settings().max_csv_bytes:
        raise HTTPException(413, "CSV exceeds upload limit")
    return import_csv(db, deck_id, data)


@router.post("/decks/{deck_id}/sessions", response_model=SessionOut, status_code=201)
def start_session(deck_id: UUID, limit: int = Query(10, ge=1, le=100), tag: str | None = Query(None, max_length=60),
                  user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    owned_deck(db, user.id, deck_id)
    batch = list(db.scalars(select(Card).join(CardState).where(
        Card.deck_id == deck_id, CardState.due_at <= utcnow()).order_by(CardState.due_at, Card.id)))
    if tag:
        batch = [card for card in batch if tag.strip().casefold() in card.tags]
    batch = batch[:limit]
    if not batch:
        raise HTTPException(409, "No cards are due right now")
    session = ReviewSession(user_id=user.id, deck_id=deck_id,
                            items=[SessionItem(card_id=card.id) for card in batch])
    db.add(session)
    db.commit()
    return {"id": session.id, "cards": batch}


@router.post("/reviews", response_model=ReviewOut)
def review(data: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    try:
        return submit_review(db, user.id, data)
    except IntegrityError:
        db.rollback()
        # A concurrent retry can insert the same id before this transaction commits.
        return submit_review(db, user.id, data)


@router.post("/sessions/{session_id}/complete", response_model=Message)
def complete(session_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return finish_session(db, user.id, session_id)


@router.post("/cards/{card_id}/images", response_model=ImageOut, status_code=201)
def upload_image(card_id: UUID, side: Literal["front", "back"], file: UploadFile = File(...),
                  user: User = Depends(current_user), db: Session = Depends(get_db),
                  store: MediaStore = Depends(get_media_store)) -> CardImage:
    card = owned_card(db, user.id, card_id)
    if len(card.images) >= get_settings().max_images_per_card:
        raise HTTPException(422, "Card image limit reached")
    data = normalize_image(file.file.read(get_settings().max_image_bytes + 1))
    image = CardImage(card_id=card.id, side=side, file_hash=store.save(user.id, data))
    db.add(image)
    db.commit()
    return image


@router.get("/cards/{card_id}/images/{image_id}", response_class=Response)
def get_image(card_id: UUID, image_id: UUID, user: User = Depends(current_user),
               db: Session = Depends(get_db), store: MediaStore = Depends(get_media_store)) -> Response:
    card = owned_card(db, user.id, card_id)
    image = next((image for image in card.images if image.id == image_id), None)
    if not image:
        raise HTTPException(404, "Image not found")
    try:
        with store.open(image.file_hash) as stream:
            return Response(stream.read(), media_type="image/webp", headers={
                "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})
    except FileNotFoundError:
        raise HTTPException(404, "Image file missing; restore the media backup")


@router.delete("/cards/{card_id}/images/{image_id}", response_model=Message)
def delete_image(card_id: UUID, image_id: UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db), store: MediaStore = Depends(get_media_store)) -> dict:
    card = owned_card(db, user.id, card_id)
    image = next((image for image in card.images if image.id == image_id), None)
    if not image:
        raise HTTPException(404, "Image not found")
    if not getattr(card, image.side).strip() and sum(i.side == image.side for i in card.images) == 1:
        raise HTTPException(422, "Add text before removing this side's last image")
    file_hash = image.file_hash
    db.delete(image)
    db.commit()
    remove_unreferenced(db, store, {file_hash})
    return {"detail": "Image deleted"}

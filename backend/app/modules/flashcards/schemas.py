from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Rating = Literal["again", "hard", "good", "easy"]


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Subject cannot be blank")
        return value.strip()


class DeckIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    subject: str = Field(default="", max_length=120)

    @field_validator("subject")
    @classmethod
    def clean_subject(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class DeckOut(DeckIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    due_count: int = 0
    ready_count: int = 0
    card_count: int = 0


class CardIn(BaseModel):
    front: str = Field(max_length=20000)
    back: str = Field(max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    choices: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        values = list(dict.fromkeys(value.strip().casefold() for value in values if value.strip()))
        if any(len(value) > 60 for value in values):
            raise ValueError("Tags must be 60 characters or fewer")
        return values

    @model_validator(mode="after")
    def validate_choices(self):
        self.choices = list(dict.fromkeys(value.strip() for value in self.choices if value.strip()))
        if self.choices and (len(self.choices) < 2 or self.back.strip() not in self.choices or any(len(v) > 20000 for v in self.choices)):
            raise ValueError("Provide 2–6 distinct choices including the exact answer")
        return self


class DraftRequest(BaseModel):
    notes: str = Field(min_length=20, max_length=16000)
    count: int = Field(default=10, ge=1, le=20)


class DraftBatch(BaseModel):
    cards: list[CardIn] = Field(min_length=1, max_length=20)


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    side: Literal["front", "back"]


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    due_at: datetime
    interval_days: float
    ease: float
    reps: int
    lapses: int
    last_reviewed_at: datetime | None
    version: int
    stability: float | None
    difficulty: float | None
    phase: int
    learning_step: int | None


class CardOut(CardIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    deck_id: UUID
    images: list[ImageOut]
    state: StateOut


class SessionOut(BaseModel):
    id: UUID
    cards: list[CardOut]


class ReviewIn(BaseModel):
    id: UUID
    card_id: UUID
    session_id: UUID
    rating: Rating
    version: int = Field(ge=0)
    reviewed_at: datetime

    @field_validator("reviewed_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("reviewed_at must include a timezone")
        return value


class ReviewOut(BaseModel):
    id: UUID
    duplicate: bool


class ImportOut(BaseModel):
    imported: int
    skipped: int
    errors: list[str]

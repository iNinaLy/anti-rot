from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PreferenceIn(BaseModel):
    daily_limit: int = Field(default=8, ge=5, le=10)
    reduce_crime: bool = True
    excluded_keywords: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("excluded_keywords")
    @classmethod
    def clean(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip().casefold() for value in values if value.strip()))
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("Excluded phrases must be 80 characters or fewer")
        return cleaned


class ArticleOut(BaseModel):
    id: UUID
    title: str
    excerpt: str
    source: str
    category: Literal["malaysia", "world", "discovery"]
    published_at: datetime
    url: str
    read: bool


class BriefingOut(BaseModel):
    date: date
    items: list[ArticleOut]
    read_count: int
    total: int
    caught_up: bool
    unavailable_sources: list[str]
    preferences: PreferenceIn


class ReadIn(BaseModel):
    read: bool

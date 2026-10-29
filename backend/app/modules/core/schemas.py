from uuid import UUID
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ActivityOut(BaseModel):
    type: str
    label: str
    completions: int
    points: int


class TodayOut(BaseModel):
    streak: int
    points: int
    activities: list[ActivityOut]


class Message(BaseModel):
    detail: str


class ActivityDay(BaseModel):
    date: date
    completions: int
    points: int


class StatsOut(BaseModel):
    completions: int
    points: int
    active_days: int
    days: list[ActivityDay]

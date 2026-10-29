from datetime import date
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PlanIn(BaseModel):
    name: str = Field(default="Nourish Move Love", min_length=1, max_length=120)
    total_days: int = Field(default=30, ge=1, le=365)
    playlist_url: str = "https://www.youtube.com/playlist?list=PLpa0d6IJAhbgN8nyV8BK-GqN_A8CXgu9c"
    workout_links: list[str] = Field(default_factory=list, max_length=365)
    current_day: int = Field(ge=1, le=366)

    @model_validator(mode="after")
    def valid_plan(self):
        if self.current_day > self.total_days + 1:
            raise ValueError("Next session exceeds the plan length")
        if len(self.workout_links) > self.total_days:
            raise ValueError("Too many workout links for this plan")
        for link in [self.playlist_url, *self.workout_links]:
            if not link:
                continue
            url = urlparse(link)
            if len(link) > 2048 or url.scheme != "https" or url.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be") or url.username or url.password or url.port not in (None, 443):
                raise ValueError("Use HTTPS YouTube video or playlist links")
        return self
    weekdays: list[int] = Field(min_length=0, max_length=7)
    reminder_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    reminders: bool
    version: int = Field(ge=0)

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, values: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in values) or len(set(values)) != len(values):
            raise ValueError("Select unique weekdays from Monday=0 to Sunday=6")
        return sorted(values)


class ExerciseOut(PlanIn):
    timezone: str = "Asia/Kuala_Lumpur"
    today_kind: Literal["strength", "walk"]
    today_date: date
    completed_today: bool
    today_day: int | None
    completed_days: list[int]
    playlist_url: str
    progress_percent: int
    completed_count: int
    workout_url: str


class CompleteIn(BaseModel):
    id: UUID
    kind: Literal["strength", "walk"]
    day: int | None = Field(default=None, ge=1, le=365)
    version: int = Field(ge=0)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=4096)
    keys: dict[str, str]

    @field_validator("endpoint")
    @classmethod
    def valid_endpoint(cls, value: str) -> str:
        url = urlparse(value)
        host = (url.hostname or "").lower()
        allowed = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com")
        if (url.scheme != "https" or url.username or url.password or url.port not in (None, 443)
                or not (host in allowed or host.endswith(".push.services.mozilla.com")
                        or host.endswith(".notify.windows.com") or host.endswith(".push.apple.com"))):
            raise ValueError("Use a supported browser push service endpoint")
        return value

    @field_validator("keys")
    @classmethod
    def valid_keys(cls, value: dict[str, str]) -> dict[str, str]:
        import base64
        try:
            public = base64.urlsafe_b64decode(value["p256dh"] + "==")
            auth = base64.urlsafe_b64decode(value["auth"] + "==")
            if len(public) != 65 or public[0] != 4 or len(auth) != 16:
                raise ValueError()
        except (KeyError, ValueError):
            raise ValueError("Invalid push subscription keys") from None
        return {key: value[key] for key in ("p256dh", "auth")}


class PushKeyOut(BaseModel):
    public_key: str

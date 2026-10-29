from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RewardIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cost: int = Field(ge=1, le=1000000)

    @field_validator("name")
    @classmethod
    def clean(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a reward name")
        return value.strip()


class RewardOut(RewardIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class RedemptionIn(BaseModel):
    id: UUID
    reward_id: UUID


class RedemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    cost: int
    redeemed_at: datetime


class WalletOut(BaseModel):
    earned: int
    spent: int
    balance: int
    rewards: list[RewardOut]
    history: list[RedemptionOut]

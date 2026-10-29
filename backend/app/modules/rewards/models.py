from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class Reward(Base):
    __tablename__ = "rewards"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    cost: Mapped[int] = mapped_column()
    active: Mapped[bool] = mapped_column(default=True)


class RewardWallet(Base):
    __tablename__ = "reward_wallets"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    version: Mapped[int] = mapped_column(default=0)


class Redemption(Base):
    __tablename__ = "redemptions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    reward_id: Mapped[UUID] = mapped_column(ForeignKey("rewards.id"))
    name: Mapped[str] = mapped_column(String(200))
    cost: Mapped[int] = mapped_column()
    redeemed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

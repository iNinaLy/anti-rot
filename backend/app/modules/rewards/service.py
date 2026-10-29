from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.core.models import ActivityCompletion
from app.modules.rewards.models import Redemption, Reward, RewardWallet
from app.modules.rewards.schemas import RedemptionIn


def owned_reward(db: Session, user_id: UUID, reward_id: UUID) -> Reward:
    reward = db.scalar(select(Reward).where(Reward.id == reward_id, Reward.user_id == user_id, Reward.active.is_(True)))
    if not reward:
        raise HTTPException(404, "Reward not found")
    return reward


def wallet(db: Session, user_id: UUID) -> dict:
    earned = db.scalar(select(func.coalesce(func.sum(ActivityCompletion.points), 0)).where(ActivityCompletion.user_id == user_id))
    spent = db.scalar(select(func.coalesce(func.sum(Redemption.cost), 0)).where(Redemption.user_id == user_id))
    return {"earned": earned, "spent": spent, "balance": earned - spent,
            "rewards": list(db.scalars(select(Reward).where(Reward.user_id == user_id, Reward.active.is_(True)).order_by(Reward.cost, Reward.name))),
            "history": list(db.scalars(select(Redemption).where(Redemption.user_id == user_id).order_by(Redemption.redeemed_at.desc()).limit(20)))}


def redeem(db: Session, user_id: UUID, data: RedemptionIn) -> dict:
    existing = db.get(Redemption, data.id)
    if existing:
        if existing.user_id != user_id or existing.reward_id != data.reward_id:
            raise HTTPException(409, "Redemption ID already used")
        return wallet(db, user_id)
    reward = owned_reward(db, user_id, data.reward_id)
    lock = db.get(RewardWallet, user_id)
    if not lock:
        lock = RewardWallet(user_id=user_id)
        db.add(lock)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            lock = db.get(RewardWallet, user_id)
    acquired = db.execute(update(RewardWallet).where(RewardWallet.user_id == user_id,
        RewardWallet.version == lock.version).values(version=lock.version + 1))
    if acquired.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Balance changed. Refresh and try again.")
    if wallet(db, user_id)["balance"] < reward.cost:
        db.rollback()
        raise HTTPException(409, "Not enough points")
    db.add(Redemption(id=data.id, user_id=user_id, reward_id=reward.id, name=reward.name, cost=reward.cost))
    db.commit()
    return wallet(db, user_id)

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.core.models import User
from app.modules.core.schemas import Message
from app.modules.core.service import current_user
from app.modules.rewards.models import Reward
from app.modules.rewards.schemas import RedemptionIn, RewardIn, RewardOut, WalletOut
from app.modules.rewards.service import owned_reward, redeem, wallet

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("", response_model=WalletOut)
def get_wallet(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return wallet(db, user.id)


@router.post("/items", response_model=RewardOut, status_code=201)
def create(data: RewardIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Reward:
    reward = Reward(user_id=user.id, **data.model_dump())
    db.add(reward); db.commit()
    return reward


@router.put("/items/{reward_id}", response_model=RewardOut)
def edit(reward_id: UUID, data: RewardIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Reward:
    reward = owned_reward(db, user.id, reward_id)
    reward.name, reward.cost = data.name, data.cost
    db.commit()
    return reward


@router.delete("/items/{reward_id}", response_model=Message)
def remove(reward_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reward = owned_reward(db, user.id, reward_id)
    reward.active = False
    db.commit()
    return {"detail": "Reward removed"}


@router.post("/redeem", response_model=WalletOut)
def purchase(data: RedemptionIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return redeem(db, user.id, data)

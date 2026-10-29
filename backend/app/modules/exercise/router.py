import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.core.models import User
from app.modules.core.schemas import Message
from app.modules.core.service import current_user
from app.modules.exercise.models import PushSubscription
from app.modules.exercise.notifications import push_keys
from app.modules.exercise.schemas import CompleteIn, ExerciseOut, PlanIn, PushKeyOut, SubscriptionIn
from app.modules.exercise.service import complete, save_plan, snapshot

router = APIRouter(prefix="/exercise", tags=["exercise"])


@router.get("/plan", response_model=ExerciseOut)
def plan(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return snapshot(db, user.id)


@router.put("/plan", response_model=ExerciseOut)
def update_plan(data: PlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return save_plan(db, user.id, data)


@router.post("/complete", response_model=ExerciseOut)
def mark_complete(data: CompleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return complete(db, user.id, data)


@router.get("/push/key", response_model=PushKeyOut)
def public_key(user: User = Depends(current_user)) -> dict:
    return {"public_key": push_keys()["public"]}


@router.post("/push/subscribe", response_model=Message)
def subscribe(data: SubscriptionIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    key = hashlib.sha256(data.endpoint.encode()).hexdigest()
    subscription = db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash == key))
    if subscription and subscription.user_id != user.id:
        raise HTTPException(409, "This device is already linked to another account. Disable its reminders first.")
    if not subscription:
        subscription = PushSubscription(user_id=user.id, endpoint_hash=key)
        db.add(subscription)
    subscription.subscription = json.dumps(data.model_dump())
    db.commit()
    return {"detail": "Device reminders enabled"}


@router.post("/push/unsubscribe", response_model=Message)
def unsubscribe(data: SubscriptionIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    db.execute(delete(PushSubscription).where(PushSubscription.user_id == user.id,
        PushSubscription.endpoint_hash == hashlib.sha256(data.endpoint.encode()).hexdigest()))
    db.commit()
    return {"detail": "Device reminders disabled"}

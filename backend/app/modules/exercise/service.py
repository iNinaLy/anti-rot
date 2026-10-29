from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import utcnow
from app.modules.core.models import ActivityCompletion
from app.modules.exercise.models import ExerciseCompletion, ExercisePlan
from app.modules.exercise.schemas import CompleteIn, PlanIn

ZONE = ZoneInfo("Asia/Kuala_Lumpur")
PLAYLIST = "https://www.youtube.com/playlist?list=PLpa0d6IJAhbgN8nyV8BK-GqN_A8CXgu9c"


def get_plan(db: Session, user_id: UUID) -> ExercisePlan:
    plan = db.get(ExercisePlan, user_id)
    if not plan:
        plan = ExercisePlan(user_id=user_id)
        db.add(plan)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            plan = db.get(ExercisePlan, user_id)
    return plan


def snapshot(db: Session, user_id: UUID, now: datetime | None = None) -> dict:
    plan = get_plan(db, user_id)
    local = (now or utcnow()).astimezone(ZONE)
    days = [int(day) for day in plan.weekdays.split(",") if day]
    kind = "strength" if local.weekday() in days else "walk"
    completed = db.scalars(select(ExerciseCompletion).where(ExerciseCompletion.user_id == user_id)).all()
    today_completion = next((item for item in completed if item.local_date == local.date() and item.kind == kind), None)
    completed_days = sorted({item.day for item in completed if item.kind == "strength" and item.day is not None and item.day <= plan.total_days})
    link_day = today_completion.day if today_completion and kind == "strength" else plan.current_day
    workout_url = (plan.workout_links[link_day - 1] if link_day and link_day <= len(plan.workout_links) else "") or plan.playlist_url
    return {"name": plan.name, "total_days": plan.total_days, "workout_links": plan.workout_links,
            "completed_count": len(completed_days), "progress_percent": 100 * len(completed_days) // plan.total_days, "current_day": plan.current_day, "weekdays": days, "reminder_time": plan.reminder_time,
            "reminders": plan.reminders, "version": plan.version, "today_kind": kind,
            "today_date": local.date(), "completed_today": today_completion is not None,
            "today_day": today_completion.day if today_completion else None,
            "completed_days": completed_days,
            "playlist_url": plan.playlist_url, "workout_url": workout_url}


def save_plan(db: Session, user_id: UUID, data: PlanIn) -> dict:
    get_plan(db, user_id)
    result = db.execute(update(ExercisePlan).where(ExercisePlan.user_id == user_id,
        ExercisePlan.version == data.version).values(current_day=data.current_day,
        name=data.name, total_days=data.total_days, playlist_url=data.playlist_url, workout_links=data.workout_links,
        weekdays=",".join(map(str, data.weekdays)), reminder_time=data.reminder_time,
        reminders=data.reminders, version=data.version + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Exercise plan changed. Reload and try again.")
    db.commit()
    return snapshot(db, user_id)


def complete(db: Session, user_id: UUID, data: CompleteIn) -> dict:
    existing = db.get(ExerciseCompletion, data.id)
    if existing:
        if existing.user_id != user_id or existing.kind != data.kind or existing.day != data.day:
            raise HTTPException(409, "Completion ID already used")
        return snapshot(db, user_id)
    plan = get_plan(db, user_id)
    now = utcnow()
    local_date = now.astimezone(ZONE).date()
    if data.kind == "strength" and (data.day != plan.current_day or plan.current_day > plan.total_days):
        raise HTTPException(409, "This is not the current challenge day")
    if data.kind == "walk" and data.day is not None:
        raise HTTPException(422, "Walks do not have challenge day numbers")
    # One completion of each kind per local day; repeated clicks never skip days.
    if db.scalar(select(ExerciseCompletion).where(ExerciseCompletion.user_id == user_id,
            ExerciseCompletion.kind == data.kind, ExerciseCompletion.local_date == local_date)):
        return snapshot(db, user_id)
    result = db.execute(update(ExercisePlan).where(ExercisePlan.user_id == user_id,
        ExercisePlan.version == data.version).values(version=data.version + 1,
        current_day=plan.current_day + int(data.kind == "strength")))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Exercise plan changed. Reload and try again.")
    db.add(ExerciseCompletion(id=data.id, user_id=user_id, kind=data.kind, day=data.day,
                              local_date=local_date, completed_at=now))
    db.add(ActivityCompletion(user_id=user_id, activity_type="exercise", activity_ref=data.id,
                              points=1, completed_at=now))
    db.commit()
    return snapshot(db, user_id)

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.modules.core.models import RefreshToken, User
from app.modules.core.schemas import Credentials, Message, TodayOut, TokenOut, UserOut, StatsOut
from app.modules.core.service import (check_login_limit, current_user, digest, dummy_hash,
                                      issue_tokens, password_matches, today_summary)

router = APIRouter(prefix="/core", tags=["core"])


# Public sign-up is intentionally disabled for this private installation.
# Keep this route outline as a reference; do not expose account creation over HTTP.
# @router.post("/auth/register", response_model=TokenOut, status_code=201)
# def register(...):
#     Account creation lives in `python -m app.cli create-user` instead.


@router.post("/auth/register", response_model=Message, include_in_schema=False)
def registration_disabled() -> dict:
    """Empty sign-up placeholder; no credentials are accepted or processed."""
    raise HTTPException(404, "Not found")


@router.post("/auth/login", response_model=TokenOut)
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    email = str(data.email).lower()
    check_login_limit(db, request, email)
    user = db.scalar(select(User).where(User.email == email))
    valid = password_matches(data.password, user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    return issue_tokens(db, user, response)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = db.scalar(select(RefreshToken).where(
        RefreshToken.token_hash == digest(request.cookies.get("refresh_token", ""))))
    if not token or token.expires_at <= utcnow():
        raise HTTPException(401, "Session expired")
    user = db.get(User, token.user_id)
    # Atomic consumption makes refresh tokens single-use even across workers.
    consumed = db.execute(delete(RefreshToken).where(RefreshToken.id == token.id))
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(401, "Session expired")
    return issue_tokens(db, user, response)


@router.post("/auth/logout", response_model=Message)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    db.execute(delete(RefreshToken).where(
        RefreshToken.token_hash == digest(request.cookies.get("refresh_token", ""))))
    db.commit()
    response.delete_cookie("refresh_token", path="/api/core/auth")
    return {"detail": "Signed out"}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.get("/today", response_model=TodayOut)
def today(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {**today_summary(db, user.id), "activities": [module.activity_provider(db, user.id)
            for module in request.app.state.modules if module.activity_provider]}


@router.get("/stats", response_model=StatsOut)
def stats(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    from collections import Counter
    from datetime import timedelta
    from app.modules.core.models import ActivityCompletion
    today = utcnow().date()
    start = today - timedelta(days=364)
    rows = db.scalars(select(ActivityCompletion).where(ActivityCompletion.user_id == user.id)).all()
    counts, points = Counter(), Counter()
    for row in rows:
        counts[row.completed_at.date()] += 1
        points[row.completed_at.date()] += row.points
    return {"completions": len(rows), "points": sum(row.points for row in rows), "active_days": len(counts),
            "days": [{"date": start + timedelta(days=index), "completions": counts[start + timedelta(days=index)],
                       "points": points[start + timedelta(days=index)]} for index in range(365)]}




class StudyScheduleIn(BaseModel):
    days: list[list[str]] = Field(min_length=7, max_length=7)


@router.get("/study-schedule")
def study_schedule(user: User = Depends(current_user)) -> dict:
    return {"days": user.study_schedule}


@router.put("/study-schedule")
def update_study_schedule(data: StudyScheduleIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if any(len(day) > 20 or any(not item.strip() or len(item) > 200 for item in day) for day in data.days):
        raise HTTPException(422, "Use up to 20 entries per day, each 1?200 characters")
    user.study_schedule = [[item.strip() for item in day] for day in data.days]
    db.commit()
    return {"days": user.study_schedule}

import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.modules.core.models import ActivityCompletion, LoginAttempt, RefreshToken, User
from app.modules.core.schemas import Credentials
from sqlalchemy.exc import IntegrityError

hasher = PasswordHasher()
dummy_hash = hasher.hash("dummy-password-for-timing")
bearer = HTTPBearer(auto_error=False)


def create_user(db: Session, credentials: Credentials) -> User:
    """Provision an account locally; intentionally not exposed through HTTP."""
    user = User(email=str(credentials.email).lower(), password_hash=hasher.hash(credentials.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Email already registered") from None
    return user


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_tokens(db: Session, user: User, response: Response) -> dict:
    settings = get_settings()
    now = utcnow()
    access = jwt.encode({"sub": str(user.id), "type": "access", "iat": now,
                         "exp": now + timedelta(minutes=settings.access_token_minutes)},
                        settings.secret_key, algorithm="HS256")
    refresh = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user.id, token_hash=digest(refresh),
                        expires_at=now + timedelta(days=settings.refresh_token_days)))
    db.commit()
    response.set_cookie("refresh_token", refresh, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", path="/api/core/auth",
                        max_age=settings.refresh_token_days * 86400)
    return {"access_token": access, "user": user}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    try:
        if credentials is None:
            raise ValueError()
        payload = jwt.decode(credentials.credentials, get_settings().secret_key, algorithms=["HS256"],
                             options={"require": ["sub", "exp", "iat", "type"]})
        if payload["type"] != "access":
            raise ValueError()
        user = db.get(User, UUID(payload["sub"]))
        if not user:
            raise ValueError()
        return user
    except (ValueError, jwt.InvalidTokenError):
        raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})


def check_login_limit(db: Session, request: Request, email: str) -> None:
    settings = get_settings()
    cutoff = utcnow() - timedelta(seconds=settings.login_window_seconds)
    # Limit IP and account independently; never trust forwarded headers.
    keys = [digest("ip:" + (request.client.host if request.client else "unknown")), digest("email:" + email)]
    db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
    for key in keys:
        count = db.scalar(select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.key == key, LoginAttempt.attempted_at >= cutoff))
        if count >= settings.login_attempts:
            db.commit()
            raise HTTPException(429, "Too many attempts. Try again later.",
                                headers={"Retry-After": str(settings.login_window_seconds)})
    db.add_all([LoginAttempt(key=key) for key in keys])
    db.commit()


def password_matches(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False


def today_summary(db: Session, user_id: UUID) -> dict:
    today = utcnow().date()
    rows = db.scalars(select(ActivityCompletion).where(ActivityCompletion.user_id == user_id)).all()
    days = {row.completed_at.date() for row in rows}
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    todays = [row for row in rows if row.completed_at.date() == today]
    return {"streak": streak, "points": sum(row.points for row in todays)}


def activity_summary(db: Session, user_id: UUID, kind: str, label: str) -> dict:
    rows = db.scalars(select(ActivityCompletion).where(
        ActivityCompletion.user_id == user_id, ActivityCompletion.activity_type == kind)).all()
    rows = [row for row in rows if row.completed_at.date() == utcnow().date()]
    return {"type": kind, "label": label, "completions": len(rows), "points": sum(row.points for row in rows)}

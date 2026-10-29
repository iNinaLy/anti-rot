from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.core.models import User
from app.modules.core.schemas import Message
from app.modules.core.service import current_user
from app.modules.news.schemas import BriefingOut, PreferenceIn, ReadIn
from app.modules.news.service import get_briefing, mark_read, preference_dict, preferences, save_preferences

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/briefing", response_model=BriefingOut)
def briefing(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return get_briefing(db, user.id)


@router.get("/preferences", response_model=PreferenceIn)
def get_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return preference_dict(preferences(db, user.id))


@router.put("/preferences", response_model=PreferenceIn)
def update_preferences(data: PreferenceIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return save_preferences(db, user.id, data)


@router.put("/stories/{article_id}/read", response_model=Message)
def read_story(article_id: UUID, data: ReadIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return mark_read(db, user.id, article_id, data.read)

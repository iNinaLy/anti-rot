from app.modules.core.service import activity_summary
from app.modules.exercise.notifications import reminder_tick
from app.modules.exercise.router import router
from app.registry import Module

module = Module("exercise", router, lambda db, user_id:
                activity_summary(db, user_id, "exercise", "Exercise"), reminder_tick)

from app.modules.core.service import activity_summary
from app.modules.flashcards.router import router
from app.modules.flashcards.drafts import router as draft_router
from app.registry import Module

router.include_router(draft_router)
module = Module("flashcards", router, lambda db, user_id:
                activity_summary(db, user_id, "flashcards", "Flashcards"))

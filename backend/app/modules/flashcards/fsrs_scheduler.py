from dataclasses import replace
from datetime import datetime, timedelta

from fsrs import Card, Rating as FSRSRating, Scheduler as FSRSEngine, State

from app.modules.flashcards.scheduler import SchedulingState
from app.modules.flashcards.schemas import Rating


class FSRS:
    """FSRS-6 memory model with Anki-style learning and relearning steps.

    The maintained engine owns the equations. We persist all memory/step fields
    explicitly and disable random interval fuzz so offline retries are repeatable.
    """

    def __init__(self, desired_retention: float = 0.9):
        self.engine = FSRSEngine(
            desired_retention=desired_retention,
            learning_steps=(timedelta(minutes=1), timedelta(minutes=10)),
            relearning_steps=(timedelta(minutes=10),),
            enable_fuzzing=False,
        )

    def next_state(self, card_state: SchedulingState, rating: Rating,
                   now: datetime) -> SchedulingState:
        if now.tzinfo is None:
            raise ValueError("Review timestamp must include a timezone")
        card = Card(card_id=0, state=State(card_state.phase), step=card_state.learning_step,
                    stability=card_state.stability, difficulty=card_state.difficulty,
                    due=card_state.due_at, last_review=card_state.last_reviewed_at)
        grades = {"again": FSRSRating.Again, "hard": FSRSRating.Hard,
                  "good": FSRSRating.Good, "easy": FSRSRating.Easy}
        updated, _ = self.engine.review_card(card, grades[rating], review_datetime=now)
        return replace(card_state, due_at=updated.due,
                       interval_days=(updated.due - now).total_seconds() / 86400,
                       reps=card_state.reps + 1,
                       lapses=card_state.lapses + int(rating == "again" and card_state.phase == State.Review),
                       last_reviewed_at=now, stability=updated.stability, difficulty=updated.difficulty,
                       phase=int(updated.state), learning_step=updated.step)

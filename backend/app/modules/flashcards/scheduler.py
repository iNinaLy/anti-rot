from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.flashcards.schemas import Rating


@dataclass(frozen=True)
class SchedulingState:
    due_at: datetime
    interval_days: float = 0
    ease: float = 2.5
    reps: int = 0
    lapses: int = 0
    last_reviewed_at: datetime | None = None
    stability: float | None = None
    difficulty: float | None = None
    phase: int = 1  # FSRS: Learning=1, Review=2, Relearning=3
    learning_step: int | None = 0


class Scheduler(Protocol):
    def next_state(self, card_state: SchedulingState, rating: Rating,
                   now: datetime) -> SchedulingState: ...

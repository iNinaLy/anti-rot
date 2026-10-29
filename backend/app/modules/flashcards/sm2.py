from datetime import datetime, timedelta

from app.modules.flashcards.scheduler import SchedulingState
from app.modules.flashcards.schemas import Rating


class SM2:
    """SM-2 with four UI ratings mapped to quality 1, 3, 4, 5."""

    def next_state(self, card_state: SchedulingState, rating: Rating,
                   now: datetime) -> SchedulingState:
        quality = {"again": 1, "hard": 3, "good": 4, "easy": 5}[rating]
        ease = max(1.3, card_state.ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if quality < 3:
            interval, reps, lapses = 1.0, 0, card_state.lapses + 1
        else:
            reps, lapses = card_state.reps + 1, card_state.lapses
            interval = (1.0 if reps == 1 else 6.0 if reps == 2
                        else float(round(card_state.interval_days * card_state.ease)))
        return SchedulingState(now + timedelta(days=interval), interval, ease, reps, lapses, now)

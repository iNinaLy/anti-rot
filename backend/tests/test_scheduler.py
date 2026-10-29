from datetime import datetime, timedelta, timezone

import pytest

from app.modules.flashcards.scheduler import SchedulingState
from app.modules.flashcards.sm2 import SM2

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


@pytest.mark.parametrize("rating,ease,reps,lapses", [
    ("again", 1.96, 0, 1), ("hard", 2.36, 1, 0), ("good", 2.5, 1, 0), ("easy", 2.6, 1, 0),
])
def test_initial_ratings(rating, ease, reps, lapses):
    result = SM2().next_state(SchedulingState(NOW), rating, NOW)
    assert result.interval_days == 1
    assert result.due_at == NOW + timedelta(days=1)
    assert result.ease == pytest.approx(ease)
    assert (result.reps, result.lapses, result.last_reviewed_at) == (reps, lapses, NOW)


def test_good_sequence():
    state = SchedulingState(NOW)
    for expected in [1, 6, 15, 38]:
        state = SM2().next_state(state, "good", state.due_at)
        assert state.interval_days == expected


def test_lapse_and_ease_floor():
    state = SchedulingState(NOW, 25, 1.3, 5, 3)
    result = SM2().next_state(state, "again", NOW)
    assert (result.interval_days, result.ease, result.reps, result.lapses) == (1, 1.3, 0, 4)
    assert state.reps == 5  # Input is immutable.

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler, State
import pytest

from app.modules.flashcards.fsrs_scheduler import FSRS
from app.modules.flashcards.scheduler import SchedulingState

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


@pytest.mark.parametrize("rating,seconds,phase,step,stability,difficulty", [
    ("again", 60, 1, 0, .212, 6.4133),
    ("hard", 330, 1, 0, 1.2931, 5.112170705601056),
    ("good", 600, 1, 1, 2.3065, 2.118103970459016),
    ("easy", 8 * 86400, 2, None, 8.2956, 1.0),
])
def test_fsrs6_known_initial_outputs(rating, seconds, phase, step, stability, difficulty):
    original = SchedulingState(NOW)
    actual = FSRS().next_state(original, rating, NOW)
    assert actual.due_at == NOW + timedelta(seconds=seconds)
    assert actual.interval_days == pytest.approx(seconds / 86400)
    assert (actual.phase, actual.learning_step) == (phase, step)
    assert actual.stability == pytest.approx(stability)
    assert actual.difficulty == pytest.approx(difficulty)
    assert actual.last_reviewed_at == NOW
    assert original.stability is None


def test_learning_graduation_lapse_and_relearning_match_reference():
    adapter, reference = FSRS(), Scheduler(enable_fuzzing=False)
    actual, card = SchedulingState(NOW), Card(card_id=0, due=NOW)
    grades = [("good", Rating.Good), ("good", Rating.Good),
              ("again", Rating.Again), ("good", Rating.Good), ("easy", Rating.Easy)]
    now = NOW
    for index, (name, grade) in enumerate(grades):
        actual = adapter.next_state(actual, name, now)
        card, _ = reference.review_card(card, grade, review_datetime=now)
        assert (actual.phase, actual.learning_step, actual.due_at) == (card.state, card.step, card.due)
        assert actual.stability == pytest.approx(card.stability)
        assert actual.difficulty == pytest.approx(card.difficulty)
        if index == 1:
            assert actual.phase == State.Review
        if index == 2:
            assert actual.phase == State.Relearning
            assert actual.lapses == 1
        # Persistence round-trip must retain every FSRS field, including step=None.
        actual = SchedulingState(**asdict(actual))
        now = actual.due_at
    assert actual.reps == 5 and actual.lapses == 1


def test_higher_retention_shortens_interval_and_retries_are_deterministic():
    state = SchedulingState(NOW)
    normal = FSRS(.9).next_state(state, "easy", NOW)
    assert FSRS(.97).next_state(state, "easy", NOW).due_at < normal.due_at
    assert FSRS(.9).next_state(state, "easy", NOW) == normal


def test_requires_timezone():
    with pytest.raises(ValueError, match="timezone"):
        FSRS().next_state(SchedulingState(NOW), "good", NOW.replace(tzinfo=None))

"""Persist FSRS memory and reconstruct it from historical reviews.

Existing due dates, versions, counters and review logs are deliberately retained.
The fsrs dependency is pinned to 6.3.2 for reproducible replay.
"""
from datetime import timezone

from alembic import op
from fsrs import Card, Rating, Scheduler
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("scheduler", sa.String(16), nullable=False, server_default="sm2"))
    op.add_column("card_states", sa.Column("stability", sa.Float(), nullable=True))
    op.add_column("card_states", sa.Column("difficulty", sa.Float(), nullable=True))
    op.add_column("card_states", sa.Column("phase", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("card_states", sa.Column("learning_step", sa.Integer(), nullable=True))
    connection = op.get_bind()
    metadata = sa.MetaData()
    states = sa.Table("card_states", metadata, autoload_with=connection)
    reviews = sa.Table("reviews", metadata, autoload_with=connection)
    scheduler = Scheduler(enable_fuzzing=False)
    ratings = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}
    for row in connection.execute(sa.select(states.c.card_id)).all():
        card = Card(card_id=0)
        history = connection.execute(sa.select(reviews).where(reviews.c.card_id == row.card_id)
                                     .order_by(reviews.c.reviewed_at, reviews.c.id)).mappings()
        for review in history:
            when = review["reviewed_at"]
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            card, _ = scheduler.review_card(card, ratings[review["rating"]], review_datetime=when)
        connection.execute(states.update().where(states.c.card_id == row.card_id).values(
            stability=card.stability, difficulty=card.difficulty,
            phase=int(card.state), learning_step=card.step))


def downgrade() -> None:
    for column in ("learning_step", "phase", "difficulty", "stability"):
        op.drop_column("card_states", column)
    op.drop_column("reviews", "scheduler")

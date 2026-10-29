"""Exercise challenge progress, daily walks and Web Push subscriptions."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("exercise_plans",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("current_day", sa.Integer(), nullable=False),
        sa.Column("weekdays", sa.String(13), nullable=False),
        sa.Column("reminder_time", sa.String(5), nullable=False),
        sa.Column("reminders", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False))
    op.create_table("exercise_completions", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False), sa.Column("day", sa.Integer(), nullable=True),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_exercise_completions_user_id", "exercise_completions", ["user_id"])
    op.create_table("push_subscriptions", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("subscription", sa.Text(), nullable=False),
        sa.Column("last_sent_date", sa.Date(), nullable=True))
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    op.drop_table("exercise_completions")
    op.drop_table("exercise_plans")

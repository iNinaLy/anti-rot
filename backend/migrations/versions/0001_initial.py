"""Initial core and flashcards schema. Frozen independently of application models."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("email", sa.String(320), nullable=False, unique=True),
                    sa.Column("password_hash", sa.String(255), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("refresh_tokens", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_table("login_attempts", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("key", sa.String(64), nullable=False),
                    sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_login_attempts_key", "login_attempts", ["key"])
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])
    op.create_table("activity_completions", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("activity_type", sa.String(64), nullable=False),
                    sa.Column("activity_ref", sa.Uuid(), nullable=False),
                    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("points", sa.Integer(), nullable=False),
                    sa.UniqueConstraint("user_id", "activity_type", "activity_ref"))
    op.create_index("ix_activity_completions_user_id", "activity_completions", ["user_id"])
    op.create_index("ix_activity_completions_completed_at", "activity_completions", ["completed_at"])
    op.create_table("decks", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("name", sa.String(200), nullable=False),
                    sa.Column("description", sa.Text(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_decks_user_id", "decks", ["user_id"])
    op.create_table("cards", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("deck_id", sa.Uuid(), sa.ForeignKey("decks.id"), nullable=False),
                    sa.Column("front", sa.Text(), nullable=False), sa.Column("back", sa.Text(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_cards_deck_id", "cards", ["deck_id"])
    op.create_table("card_states", sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id"), primary_key=True),
                    sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("interval_days", sa.Float(), nullable=False), sa.Column("ease", sa.Float(), nullable=False),
                    sa.Column("reps", sa.Integer(), nullable=False), sa.Column("lapses", sa.Integer(), nullable=False),
                    sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
                    sa.Column("version", sa.Integer(), nullable=False))
    op.create_index("ix_card_states_due_at", "card_states", ["due_at"])
    op.create_table("review_sessions", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("deck_id", sa.Uuid(), sa.ForeignKey("decks.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_review_sessions_user_id", "review_sessions", ["user_id"])
    op.create_table("session_items",
                    sa.Column("session_id", sa.Uuid(), sa.ForeignKey("review_sessions.id"), primary_key=True),
                    sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id"), primary_key=True),
                    sa.Column("reviewed", sa.Boolean(), nullable=False))
    op.create_table("reviews", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id"), nullable=False),
                    sa.Column("session_id", sa.Uuid(), sa.ForeignKey("review_sessions.id"), nullable=False),
                    sa.Column("rating", sa.String(10), nullable=False),
                    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("prev_interval", sa.Float(), nullable=False),
                    sa.Column("new_interval", sa.Float(), nullable=False),
                    sa.UniqueConstraint("session_id", "card_id"))
    op.create_index("ix_reviews_card_id", "reviews", ["card_id"])
    op.create_table("card_images", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id"), nullable=False),
                    sa.Column("side", sa.String(5), nullable=False),
                    sa.Column("file_hash", sa.String(64), nullable=False))
    op.create_index("ix_card_images_card_id", "card_images", ["card_id"])
    op.create_index("ix_card_images_file_hash", "card_images", ["file_hash"])


def downgrade() -> None:
    for name in ("card_images", "reviews", "session_items", "review_sessions", "card_states",
                 "cards", "decks", "activity_completions", "login_attempts", "refresh_tokens", "users"):
        op.drop_table(name)

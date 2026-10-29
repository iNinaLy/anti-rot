"""Persist custom subjects independently from decks."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("subjects", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("name", sa.String(120), nullable=False),
                    sa.Column("name_key", sa.String(240), nullable=False),
                    sa.UniqueConstraint("user_id", "name_key"))
    op.create_index("ix_subjects_user_id", "subjects", ["user_id"])


def downgrade() -> None:
    op.drop_table("subjects")

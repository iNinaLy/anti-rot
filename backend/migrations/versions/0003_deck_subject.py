"""Organize decks by university subject; existing decks remain uncategorized."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decks", sa.Column("subject", sa.String(120), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("decks", "subject")

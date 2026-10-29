"""Save each user's editable weekly study schedule."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("study_schedule", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("study_schedule")

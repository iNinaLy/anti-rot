"""Customizable strength plan; preserve existing schedule and completions."""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exercise_plans", sa.Column("name", sa.String(120), nullable=False, server_default="Nourish Move Love"))
    op.add_column("exercise_plans", sa.Column("total_days", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("exercise_plans", sa.Column("playlist_url", sa.String(2048), nullable=False, server_default="https://www.youtube.com/playlist?list=PLpa0d6IJAhbgN8nyV8BK-GqN_A8CXgu9c"))
    op.add_column("exercise_plans", sa.Column("workout_links", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    with op.batch_alter_table("exercise_plans") as batch:
        for name in ("workout_links", "playlist_url", "total_days", "name"):
            batch.drop_column(name)

"""Remove rewards and point spending; shared activity history remains intact.

Existing reward definitions/redemptions are removed. Restore a pre-upgrade
backup to recover their data; downgrading recreates only the empty schema.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("redemptions")
    op.drop_table("reward_wallets")
    op.drop_table("rewards")


def downgrade() -> None:
    op.create_table("rewards", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False))
    op.create_index("ix_rewards_user_id", "rewards", ["user_id"])
    op.create_table("reward_wallets", sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False))
    op.create_table("redemptions", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reward_id", sa.Uuid(), sa.ForeignKey("rewards.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_redemptions_user_id", "redemptions", ["user_id"])

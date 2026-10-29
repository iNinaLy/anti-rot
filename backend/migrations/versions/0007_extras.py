"""Card tags/multiple choice, rewards and immutable redemption ledger."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("cards", sa.Column("choices", sa.JSON(), nullable=False, server_default="[]"))
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


def downgrade() -> None:
    op.drop_table("redemptions"); op.drop_table("reward_wallets"); op.drop_table("rewards")
    op.drop_column("cards", "choices"); op.drop_column("cards", "tags")

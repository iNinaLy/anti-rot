"""Finite daily RSS briefing and private reading preferences/progress."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("news_articles", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False), sa.Column("title", sa.String(500), nullable=False),
        sa.Column("excerpt", sa.String(600), nullable=False), sa.Column("source", sa.String(100), nullable=False),
        sa.Column("category", sa.String(16), nullable=False), sa.Column("tags", sa.String(500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_news_articles_category", "news_articles", ["category"])
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"])
    op.create_table("news_feed_states", sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ok", sa.Boolean(), nullable=False))
    op.create_table("news_preferences", sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("daily_limit", sa.Integer(), nullable=False), sa.Column("reduce_crime", sa.Boolean(), nullable=False),
        sa.Column("excluded_keywords", sa.Text(), nullable=False))
    op.create_table("news_briefings", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "local_date"))
    op.create_index("ix_news_briefings_user_id", "news_briefings", ["user_id"])
    op.create_table("news_briefing_items",
        sa.Column("briefing_id", sa.Uuid(), sa.ForeignKey("news_briefings.id"), primary_key=True),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("news_articles.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("read", sa.Boolean(), nullable=False))


def downgrade() -> None:
    for table in ("news_briefing_items", "news_briefings", "news_preferences", "news_feed_states", "news_articles"):
        op.drop_table(table)

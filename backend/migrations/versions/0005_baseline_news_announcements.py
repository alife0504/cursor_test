"""baseline: news_metadata + announcements.

Phase 4 baseline part 5/13。

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-12

設計：
- 不轉 hypertable（單筆量小，可手動 retention）
- qdrant_point_id 對應 Qdrant 中的 vector point
- symbol nullable — macro 新聞無 symbol，所以不設 FK
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKET_CHECK = "market IS NULL OR market IN ('TWSE', 'TPEX', 'NYSE', 'NASDAQ', 'AMEX', 'OTHER')"
_SENTIMENT_CHECK = "sentiment IN ('positive', 'neutral', 'negative', 'unknown')"


def upgrade() -> None:
    # ── news_metadata ─────────────────────────────────
    op.create_table(
        "news_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(20)),
        sa.Column("market", sa.String(50)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("source", sa.String(50)),
        sa.Column("url", sa.Text),
        sa.Column("author", sa.String(100)),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sentiment", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("sentiment_score", sa.Numeric(5, 4)),
        sa.Column("qdrant_collection", sa.String(50)),
        sa.Column("qdrant_point_id", postgresql.UUID(as_uuid=True)),
        sa.Column("word_count", sa.Integer),
        sa.Column("extra_meta", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_news_metadata_market"),
        sa.CheckConstraint(_SENTIMENT_CHECK, name="ck_news_metadata_sentiment"),
    )
    op.create_index("ix_news_metadata_symbol_published", "news_metadata",
                    ["symbol", "published_at"])
    op.create_index("ix_news_metadata_published_desc", "news_metadata", ["published_at"])
    op.create_index("ix_news_metadata_sentiment", "news_metadata", ["sentiment"])
    op.execute(
        "CREATE INDEX ix_news_metadata_extra_meta_gin "
        "ON news_metadata USING gin (extra_meta jsonb_path_ops)"
    )

    # ── announcements ──────────────────────────────────
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(20)),
        sa.Column("market", sa.String(50)),
        sa.Column("announcement_type", sa.String(100)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qdrant_collection", sa.String(50)),
        sa.Column("qdrant_point_id", postgresql.UUID(as_uuid=True)),
        sa.Column("extra_meta", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_announcements_market"),
    )
    op.create_index("ix_announcements_symbol_published", "announcements",
                    ["symbol", "published_at"])
    op.create_index("ix_announcements_published_desc", "announcements", ["published_at"])
    op.create_index("ix_announcements_type", "announcements", ["announcement_type"])


def downgrade() -> None:
    op.drop_table("announcements")
    op.execute("DROP INDEX IF EXISTS ix_news_metadata_extra_meta_gin")
    op.drop_table("news_metadata")

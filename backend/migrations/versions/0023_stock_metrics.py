"""stock_metrics —— 選股篩選器用的每檔最新指標快照（PE/殖利率/PBR/市值/RSI/EPS 成長）。

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-17

背景：
- screener 篩選器頁的 PE/殖利率/EPS 成長/RSI/市值 條件與結果欄長期是「未物化」的 demo：
  screener_repo 只套 market+industry，5 個指標欄硬寫 None、對應 filter 全被忽略 →
  使用者設任何數值條件都回同一份未過濾清單（一個「篩選器」核心功能靜默無效）。
- 逐次查詢即時計算全市場 2,375 檔的 PE/RSI 太貴；正解是物化成每檔一列的快照表，由每日
  排程刷新，screener 直接 JOIN + WHERE。

資料來源：
- PER / PBR / dividend_yield：FinMind TaiwanStockPER（本地庫 bronze.taiwan_stock_per，
  近日缺口用 API bulk 補）。
- market_cap：FinMind TaiwanStockMarketValue（bronze.taiwan_stock_market_value）。
- rsi14：由 app 的 stock_prices 近 ~30 日收盤計算（reuse screening_service._rsi）。
- eps_growth：financial_statements 最新一季 EPS 對去年同季 YoY（typed eps 欄，已於本輪填好）。

每檔一列（symbol PK）；只保留最新快照（非時序），故不轉 hypertable。
新表由 ta_migration 建立 → ALTER DEFAULT PRIVILEGES 自動授 SELECT/INSERT/UPDATE 給
ta_service_rw（同 institutional_trading / margin_trading，不需在此明列 grant）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_metrics",
        sa.Column("symbol", sa.String(20), nullable=False),
        # 指標對應的資料日（PER/市值的 as-of；RSI 用最新收盤日）
        sa.Column("as_of_date", sa.Date, nullable=True),
        sa.Column("pe_ratio", sa.Numeric(12, 4)),
        sa.Column("pbr", sa.Numeric(12, 4)),
        sa.Column("dividend_yield", sa.Numeric(8, 4)),  # 百分比，如 0.9 = 0.9%
        sa.Column("market_cap", sa.BigInteger),  # TWD
        sa.Column("rsi14", sa.Numeric(6, 2)),
        sa.Column("eps_growth", sa.Numeric(12, 4)),  # YoY 百分比，如 15.5 = +15.5%
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("symbol", name="pk_stock_metrics"),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_stock_metrics_symbol_stock_list",
        ),
    )
    # screener 常用範圍過濾欄位加索引（部分掃描仍可，但常見排序/範圍受益）
    op.create_index("ix_stock_metrics_pe_ratio", "stock_metrics", ["pe_ratio"])
    op.create_index("ix_stock_metrics_market_cap", "stock_metrics", ["market_cap"])
    op.create_index("ix_stock_metrics_dividend_yield", "stock_metrics", ["dividend_yield"])


def downgrade() -> None:
    op.drop_index("ix_stock_metrics_dividend_yield", table_name="stock_metrics")
    op.drop_index("ix_stock_metrics_market_cap", table_name="stock_metrics")
    op.drop_index("ix_stock_metrics_pe_ratio", table_name="stock_metrics")
    op.drop_table("stock_metrics")

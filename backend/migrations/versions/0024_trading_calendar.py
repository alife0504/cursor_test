"""trading_calendar —— 台股「實際交易日」曆（供資料缺口偵測與 N 交易日計算）。

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-27

背景：
- 資料管線的多源合併原本只用 max(date)>=end 或 >15 天大缺口啟發式判斷涵蓋，無法精準
  偵測「單一交易日缺漏」。要精準需知道「哪些日子市場實際有開盤交易」。
- FinMind 的 taiwan_stock_trading_date 是「排程」日曆（提前發布），**不含臨時休市（颱風假）**，
  例如 2026-07-10 排程為交易日但實際全市場無成交（颱風）→ 用它會把颱風假誤判成缺口。
- 故本表存「實際交易日」＝ finmind-platform bronze.taiwan_stock_price 中「市場性有價格」
  （>500 檔）的日期；由 sync_trading_calendar_tw 每週刷新。自然排除颱風/臨時休市。

用途：
- data_pipeline 多源合併：merged 若缺任一「實際交易日」→ 續問下一來源補洞（精準，無颱風假誤觸）。
- 準確率 N 交易日 pending 判定的權威依據（未來可擴充）。

每列＝一個交易日（date, market）。新表由 ta_migration 建立 → 預設權限自動授 ta_service_rw。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trading_calendar",
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("market", sa.String(4), nullable=False, server_default="TW"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("date", "market", name="pk_trading_calendar"),
    )


def downgrade() -> None:
    op.drop_table("trading_calendar")

"""stock_prices retention 1 年 → 5 年（對齊長區間查詢窗，深度審計 #23）。

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-10

背景（深度審計發現）：
- stock_prices 原設 1 年 retention（0003），但上層契約允許遠大於 1 年的查詢窗：
  agents get_ohlcv days_back ≤ 720（近 2 年）、前端 K 線可選 3Y/5Y、get_indicators 預設 365 天。
  retention 背景 job 靜默 drop 超期 chunk → 長區間查詢/52 週高低/長均線以殘缺序列計算而失真，
  且無任何錯誤或截斷警示。
- 行情本來就是分析核心資產，不該被 1 年 retention 砍掉。將 retention 延長到 5 年，足以覆蓋
  前端 5Y 圖與所有 agent 查詢窗（720 天），同時仍有上界避免無限成長。
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 先移除舊的 1 年 policy，再加 5 年（add_retention_policy 對同表重複加會衝突，故先移除）
    op.execute("SELECT remove_retention_policy('stock_prices', if_exists => TRUE)")
    op.execute(
        "SELECT add_retention_policy('stock_prices', INTERVAL '5 years', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.execute("SELECT remove_retention_policy('stock_prices', if_exists => TRUE)")
    op.execute(
        "SELECT add_retention_policy('stock_prices', INTERVAL '1 year', if_not_exists => TRUE)"
    )

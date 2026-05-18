"""真實 FinMind API 整合測試（@pytest.mark.network — 預設 skip）。

執行方式：
    cd backend && uv run pytest tests/integration/test_real_finmind.py -m network -v

需要：
- .env 內有 FINMIND_TOKEN（可選；無 token 也可跑公開 dataset，但配額更小）
- 網路通

無 token 時：自動跳過。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.data_sources.tw.finmind_source import FinMindSource

pytestmark = pytest.mark.network


@pytest.fixture
def fm_real() -> FinMindSource:
    CIRCUIT_BREAKERS.pop("finmind", None)
    return FinMindSource(settings)


@pytest.mark.asyncio
async def test_finmind_real_call_returns_ohlcv(fm_real: FinMindSource) -> None:
    """真實打 FinMind：抓 2330 最近 ~7 天，驗 row > 0。"""
    if not settings.FINMIND_TOKEN:
        pytest.skip("FINMIND_TOKEN 未設定，跳過真實 API 測試")

    end = date.today()
    start = end - timedelta(days=14)
    df = await fm_real.fetch_ohlcv("2330", start, end)
    # 14 天裡至少有 ≥ 3 個交易日
    assert len(df) >= 3
    assert {"date", "open", "high", "low", "close", "volume"}.issubset(df.columns)
    # 收盤價應 > 0
    assert all(df["close"] > 0)

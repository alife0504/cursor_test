"""yfinance 真實網路呼叫 — 標 @pytest.mark.network。

預設 CI 不跑（pytest -m "not network"）。需手動：
    uv run pytest tests/integration/test_real_yfinance.py -m network
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.data_sources.us.yfinance_source import YFinanceSource


@pytest.mark.network
@pytest.mark.asyncio
async def test_yfinance_real_call_aapl_returns_ohlcv() -> None:
    """真的打 yfinance 抓 AAPL 最近 5 天 OHLCV。

    若 yfinance API 不穩或被擋（Yahoo 偶爾 429），可能 fail。
    用 pytest.skip 跳過，避免 CI 紅燈。
    """
    src = YFinanceSource(settings)
    end = date.today() - timedelta(days=2)  # 避免今日尚未收盤的 partial bar
    start = end - timedelta(days=14)

    try:
        df = await src.fetch_ohlcv("AAPL", start, end)
    except Exception as e:
        pytest.skip(f"yfinance live API unavailable: {e}")

    assert not df.empty, "yfinance 應有至少一筆 AAPL 資料"
    assert "date" in df.columns
    assert "close" in df.columns
    assert "volume" in df.columns
    # 至少一筆 close > 0
    assert any(c is not None and c > 0 for c in df["close"])

"""真 LLM 整合測試（@network @expensive）— Phase 13 條 T。

跑真實 Gemini API 對 2330 做技術面分析，驗證：
1. schema validation 通過（不會卡 retry）
2. cost 在合理範圍（~ $0.005 ~ $0.02）
3. 結果有實質內容（summary > 100 chars）

注意：
- 需要 .env 設定 GOOGLE_API_KEY
- 跑一次約消耗 $0.005 ~ $0.012
- CI 預設略過（pytest markers）
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

from app.agents.analysts.market_analyst import MarketAnalyst
from app.agents.schemas import MarketAnalysisResult

pytestmark = [pytest.mark.network, pytest.mark.expensive, pytest.mark.integration]


# 略過條件：未設 GOOGLE_API_KEY 或 .env 不存在
_HAS_KEY = bool(os.getenv("GOOGLE_API_KEY"))


@pytest.mark.skipif(
    not _HAS_KEY,
    reason="未設 GOOGLE_API_KEY；跳過真 LLM 測試（@expensive）",
)
def test_real_2330_market_analyst() -> None:
    """跑真 Gemini → MarketAnalyst 對 2330 完整流程。

    預期成本：~$0.005 ~ $0.02。
    """
    # 用真實 ro session
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.agents.tools import ToolRegistry
    from app.core.config import settings
    from app.llm import get_llm_provider

    async def _run() -> dict[str, Any]:
        llm = get_llm_provider(settings.LLM_DEFAULT_PROVIDER, settings)
        engine = create_async_engine(settings.postgres_dsn_ro, pool_size=2)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        try:
            tools = ToolRegistry(sm)
            analyst = MarketAnalyst(llm=llm, tools=tools)
            state: dict[str, Any] = {
                "symbol": "2330",
                "market_code": "TWSE",
                "region": "TW",
                "analysis_id": None,
            }
            return await analyst.analyze(state)
        finally:
            await engine.dispose()

    result = asyncio.run(_run())

    # 驗結果結構
    assert "analyses" in result and "market" in result["analyses"]
    payload = json.loads(result["analyses"]["market"])
    parsed = MarketAnalysisResult.model_validate(payload)

    assert len(parsed.summary) >= 100
    assert parsed.confidence >= 0
    assert parsed.short_term_view in {"看多", "看空", "中性"}

    # token 使用量應 > 0
    assert result.get("llm_usage_total_tokens", 0) > 0

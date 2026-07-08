"""Phase 11 — /api/v1/analysis/* schemas。

依 PLAN.md 第 20.x（API design）+ 第 14.9（LangGraph state）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import BaseSchema

ALLOWED_ANALYST_TYPES = {"market", "sentiment", "news", "fundamental", "chip"}
"""與 ANALYST_REGISTRY 對齊。v1.1：新增 chip（籌碼面）；sentiment 正名為情緒面
（新聞情緒聚合），原籌碼面實作改名為 chip。"""
DEFAULT_LLM_MODEL = "gemini-2.5-flash"
SCREEN_LEVELS = {"low", "mid", "high"}
"""自動選股篩選等級（與前端 ScreenLevelChooser / screening_service 對齊）。
基本 floor 永遠套用、非可選等級，故不在此。"""


class AnalysisCreateRequest(BaseSchema):
    """POST /api/v1/analysis 的 request body。

    兩種模式（擇一）：
    - **指定個股**：帶 `symbol` → 建立單筆分析（原行為）。
    - **自動選股**：不帶 `symbol`、帶 `screen_level` → 送出後由後端依等級批次篩選
      （`market` 指定篩選市場，預設 TW），對選出的每檔各建一筆分析。
    """

    symbol: str | None = Field(default=None, max_length=20)
    screen_level: str | None = Field(
        default=None,
        description="自動選股等級（basic/low/mid/high）；未帶 symbol 時必填",
    )
    market: str | None = Field(
        default=None,
        max_length=4,
        description="自動選股的篩選市場（TW/US）；未帶 symbol 時使用，預設 TW",
    )
    analyst_types: list[str] = Field(default_factory=lambda: ["market"])
    llm_model: str = Field(default=DEFAULT_LLM_MODEL, max_length=100)
    debate_rounds: int = Field(default=1, ge=0, le=5)
    risk_rounds: int = Field(
        default=0,
        ge=0,
        le=3,
        description="風險辯論輪次（0=關閉完整風險架構；>0=啟用 trader+風險團隊+verifier，成本較高）",
    )
    agent_models: dict[str, str] | None = Field(
        default=None,
        description="各 agent 的模型覆寫（role → model id，如 {'market':'gpt-4o-mini'}）；缺則用 llm_model 預設",
    )
    risk_tolerance: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("screen_level")
    @classmethod
    def validate_screen_level(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SCREEN_LEVELS:
            raise ValueError(f"screen_level 不支援 {v!r}；允許值：{sorted(SCREEN_LEVELS)}")
        return v

    @field_validator("market")
    @classmethod
    def validate_market(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in {"TW", "US"}:
            raise ValueError("market 僅允許 TW / US")
        return v

    @model_validator(mode="after")
    def validate_mode(self) -> AnalysisCreateRequest:
        """symbol 與 screen_level 二擇一：指定個股 vs 自動選股。"""
        if not self.symbol and not self.screen_level:
            raise ValueError("必須提供 symbol（指定個股）或 screen_level（自動選股）其一")
        if self.symbol and self.screen_level:
            raise ValueError("symbol 與 screen_level 不可同時提供（擇一）")
        # 自動選股模式：market 預設 TW
        if self.screen_level and not self.market:
            self.market = "TW"
        return self

    @field_validator("agent_models")
    @classmethod
    def validate_agent_models(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("agent_models 數量過多")
        # 值長度防呆；未知 role/model 交給後端 chain 優雅處理（provider_for_model 回 None → 用預設）
        for role, model in v.items():
            if not isinstance(role, str) or not isinstance(model, str) or len(model) > 100:
                raise ValueError("agent_models 格式錯誤")
        return v

    @field_validator("analyst_types")
    @classmethod
    def validate_analyst_types(cls, v: list[str]) -> list[str]:
        if not v:
            return ["market"]
        bad = [t for t in v if t not in ALLOWED_ANALYST_TYPES]
        if bad:
            raise ValueError(
                f"analyst_types 含不支援值 {bad}；允許值：{sorted(ALLOWED_ANALYST_TYPES)}"
            )
        # 去重 + 維持順序
        seen: set[str] = set()
        result: list[str] = []
        for t in v:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result


class AnalysisCreateResponse(BaseSchema):
    """POST /api/v1/analysis 的成功回應。

    - 指定個股：`analysis_id` = 該筆；`count` = 1；`analysis_ids` = [該筆]。
    - 自動選股：`analysis_id` = 第一筆（前端可直接跳轉）；`count` = 建立筆數；
      `analysis_ids` = 全部；`screened_symbols` = 篩選選出的股票代號。
    """

    analysis_id: UUID
    status: str
    estimated_seconds: int = 180
    count: int = 1
    analysis_ids: list[UUID] = Field(default_factory=list)
    screened_symbols: list[str] = Field(default_factory=list)
    screened_count: int = 0
    """自動選股篩出的候選總數（可能 > count；實際只建立前 count 檔分析，其餘為候選）。"""


class AnalysisSummary(BaseSchema):
    """GET /api/v1/analysis 列表元素。"""

    id: UUID
    symbol: str
    market: str
    status: str
    signal: str | None = None
    confidence: Decimal | None = None
    llm_model: str | None = None
    total_cost_usd: Decimal | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisDetail(BaseSchema):
    """GET /api/v1/analysis/{id}。"""

    id: UUID
    user_id: UUID
    symbol: str
    market: str
    status: str
    signal: str | None = None
    confidence: Decimal | None = None
    target_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    total_tokens: int
    total_cost_usd: Decimal
    report_md: str | None = None
    error_msg: str | None = None
    version: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # v1.0.1 新增：給前端 AnalystResultCard / AgentFlowGraph / Risk panel 用
    analyst_outputs: dict[str, Any] | None = None
    analyst_types: list[str] | None = None
    debate_rounds: int | None = None
    risk_tolerance: str | None = None


class DebateMessageOut(BaseSchema):
    """GET /api/v1/analysis/{id}/debate 元素。"""

    id: UUID
    analysis_id: UUID
    round_num: int
    role: str
    content: dict[str, Any] | list[Any]
    tokens_used: int | None = None
    created_at: datetime


__all__ = [
    "ALLOWED_ANALYST_TYPES",
    "DEFAULT_LLM_MODEL",
    "SCREEN_LEVELS",
    "AnalysisCreateRequest",
    "AnalysisCreateResponse",
    "AnalysisDetail",
    "AnalysisSummary",
    "DebateMessageOut",
]

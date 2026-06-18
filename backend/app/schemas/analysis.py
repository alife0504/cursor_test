"""Phase 11 — /api/v1/analysis/* schemas。

依 PLAN.md 第 20.x（API design）+ 第 14.9（LangGraph state）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema

ALLOWED_ANALYST_TYPES = {"market", "sentiment", "news", "fundamental"}
"""P13 修正：與 SentimentAnalyst.name 對齊（P11 遺留 "social"，會擋掉合法請求）。"""
DEFAULT_LLM_MODEL = "gemini-2.5-flash"


class AnalysisCreateRequest(BaseSchema):
    """POST /api/v1/analysis 的 request body。"""

    symbol: str = Field(min_length=1, max_length=20)
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
    """POST /api/v1/analysis 的成功回應。"""

    analysis_id: UUID
    status: str
    estimated_seconds: int = 180


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
    "AnalysisCreateRequest",
    "AnalysisCreateResponse",
    "AnalysisDetail",
    "AnalysisSummary",
    "DebateMessageOut",
]

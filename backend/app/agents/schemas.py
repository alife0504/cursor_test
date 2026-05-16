"""Agent 結構化輸出 Schemas — Pydantic v2。

依 PLAN.md 第 20.3 章 Agent 輸出 schema 規範 + 第 18.2 章 Plugin Pattern。

設計：
- 每個 Analyst / Researcher / Manager 都對應一個 Schema。
- 嚴格 validation（min/max length、enum、Decimal）。
- 序列化時 Decimal → str（避免 JSON float 精度問題）。
- 反序列化時 str → Decimal（PLAN 14.9 已知陷阱）。

注意：本檔案的 Schema 不會與 DB ORM 共用（DB 用 app.models）；
此處純粹用於 LLM 結構化輸出驗證。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Analyst Result Schemas ─────────────────────────────
#
# 註：Pydantic v2 `model_dump(mode="json")` 預設會把 Decimal 轉 str（無需 json_encoders）；
# `model_dump_json()` 同樣行為。故不再用已 deprecated 的 json_encoders（v3 會移除）。


class MarketAnalysisResult(BaseModel):
    """技術面分析結果（MarketAnalyst 輸出）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=100, max_length=2000, description="技術面綜述（繁中）")
    trend: Literal["上升", "下降", "盤整", "反轉"]
    support_levels: list[Decimal] = Field(min_length=1, max_length=5)
    resistance_levels: list[Decimal] = Field(min_length=1, max_length=5)
    key_indicators: dict[str, str] = Field(
        min_length=3,
        description="{'RSI': 'xx', 'MACD': 'xx', 'MA20': 'xx', ...}",
    )
    risk_factors: list[str] = Field(min_length=1, max_length=8)
    short_term_view: Literal["看多", "看空", "中性"]
    confidence: int = Field(ge=0, le=100)


class FundamentalAnalysisResult(BaseModel):
    """基本面分析結果（FundamentalAnalyst 輸出）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=100, max_length=2000)
    valuation: Literal["低估", "合理", "高估"]
    financial_strength: Literal["強", "中", "弱"]
    growth_outlook: str = Field(min_length=20, max_length=500)
    key_ratios: dict[str, str] = Field(min_length=3)
    risk_factors: list[str] = Field(min_length=1, max_length=8)
    long_term_view: Literal["看多", "看空", "中性"]
    confidence: int = Field(ge=0, le=100)


class NewsSupportingArticle(BaseModel):
    """NewsAnalysisResult.supporting_articles 元素。"""

    title: str = Field(min_length=2, max_length=500)
    url: str = Field(min_length=4, max_length=2048)
    published_at: str = Field(description="ISO 8601 datetime string")
    score: float = Field(ge=0.0, le=1.0, description="自評相關性")


class NewsAnalysisResult(BaseModel):
    """新聞情緒分析結果（NewsAnalyst 輸出）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=100, max_length=2000)
    sentiment: Literal["極度正面", "正面", "中性", "負面", "極度負面"]
    key_topics: list[str] = Field(min_length=0, max_length=8)
    supporting_articles: list[NewsSupportingArticle] = Field(default_factory=list, max_length=8)
    impact_assessment: str = Field(min_length=10, max_length=500)
    confidence: int = Field(ge=0, le=100)


class SentimentAnalysisResult(BaseModel):
    """籌碼面分析結果（SentimentAnalyst 輸出；TW only）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=100, max_length=2000)
    institutional_flow: Literal["大量買超", "小量買超", "中性", "小量賣超", "大量賣超"]
    foreign_position_change: str = Field(min_length=10, max_length=500)
    margin_trading_signal: Literal["看多", "看空", "中性"]
    retail_sentiment: Literal["過熱", "正常", "悲觀"]
    risk_factors: list[str] = Field(min_length=1, max_length=6, default_factory=list)
    confidence: int = Field(ge=0, le=100)


# ── Researcher / Manager Schemas ────────────────────────


class BullArgument(BaseModel):
    """Bull researcher 單輪論點。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    points: list[str] = Field(min_length=3, max_length=8)
    confidence: int = Field(ge=0, le=100)
    evidence_from: list[Literal["market", "fundamental", "news", "sentiment"]] = Field(
        min_length=1,
        max_length=4,
    )


class BearArgument(BaseModel):
    """Bear researcher 單輪論點（同結構，不同立場）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    points: list[str] = Field(min_length=3, max_length=8)
    confidence: int = Field(ge=0, le=100)
    evidence_from: list[Literal["market", "fundamental", "news", "sentiment"]] = Field(
        min_length=1,
        max_length=4,
    )


class FinalSignal(BaseModel):
    """Manager 綜合決策（單一 signal）— 跨表存到 analysis_reports.signal。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["BUY", "HOLD", "SELL"]
    confidence: int = Field(ge=0, le=100)
    target_price_low: Decimal | None = None
    target_price_high: Decimal | None = None
    stop_loss: Decimal | None = None
    time_horizon: Literal["短期(1-2週)", "中期(1-3月)", "長期(>3月)"]
    position_size_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    reasoning_zh: str = Field(min_length=200, max_length=3000)
    risk_factors: list[str] = Field(min_length=1, max_length=8)
    debate_winner: Literal["bull", "bear", "neutral"]

    @field_validator("target_price_low", "target_price_high", "stop_loss", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> Decimal | None:
        """容錯：LLM 可能回 str 或 number → 統一轉 Decimal；空字串 / 'null' → None。"""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int | float):
            return Decimal(str(v))
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped or stripped.lower() in ("null", "none", "n/a", "-"):
                return None
            try:
                return Decimal(stripped)
            except Exception as e:
                raise ValueError(f"無法將 '{v}' 轉為 Decimal") from e
        raise ValueError(f"不支援的 type: {type(v).__name__}")

    @field_validator("position_size_pct", mode="before")
    @classmethod
    def _coerce_pct(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int | float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v.strip())
        raise ValueError(f"position_size_pct 不支援的 type: {type(v).__name__}")


# ── exports ────────────────────────────────────────────


__all__ = [
    "BearArgument",
    "BullArgument",
    "FinalSignal",
    "FundamentalAnalysisResult",
    "MarketAnalysisResult",
    "NewsAnalysisResult",
    "NewsSupportingArticle",
    "SentimentAnalysisResult",
]

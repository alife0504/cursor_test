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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Analyst Result Schemas ─────────────────────────────
#
# 註：Pydantic v2 `model_dump(mode="json")` 預設會把 Decimal 轉 str（無需 json_encoders）；
# `model_dump_json()` 同樣行為。故不再用已 deprecated 的 json_encoders（v3 會移除）。


class MarketAnalysisResult(BaseModel):
    """技術面分析結果（MarketAnalyst 輸出）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=40, max_length=2000, description="技術面綜述（繁中）")
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

    summary: str = Field(min_length=40, max_length=2000)
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
    """新聞/公告 + 總經分析結果（NewsAnalyst 輸出）。

    涵蓋個股新聞、重大公告，以及大盤/總體經濟脈絡（macro_context）。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=40, max_length=2000)
    sentiment: Literal["極度正面", "正面", "中性", "負面", "極度負面"]
    key_topics: list[str] = Field(min_length=0, max_length=8)
    supporting_articles: list[NewsSupportingArticle] = Field(default_factory=list, max_length=8)
    impact_assessment: str = Field(min_length=10, max_length=500)
    macro_context: str = Field(
        default="",
        max_length=800,
        description="總經/大盤脈絡：利率、通膨、外資動向、地緣政治對整體市場的影響（可空）",
    )
    macro_bias: Literal["偏多", "中性", "偏空", "未提供"] = Field(
        default="未提供",
        description="總經環境對整體市場的方向偏向（資料不足時為『未提供』）",
    )
    confidence: int = Field(ge=0, le=100)


class ChipAnalysisResult(BaseModel):
    """籌碼面分析結果（ChipAnalyst 輸出；TW only）。

    註：v1.0 前身為 `SentimentAnalysisResult`（名稱誤植為情緒面，實為籌碼面）。
    v1.1 正名為 chip；情緒面另立新 `SentimentAnalysisResult`（新聞情緒聚合）。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=40, max_length=2000)
    institutional_flow: Literal["大量買超", "小量買超", "中性", "小量賣超", "大量賣超"]
    foreign_position_change: str = Field(min_length=10, max_length=500)
    margin_trading_signal: Literal["看多", "看空", "中性"]
    retail_sentiment: Literal["過熱", "正常", "悲觀"]
    risk_factors: list[str] = Field(min_length=1, max_length=6, default_factory=list)
    confidence: int = Field(ge=0, le=100)


class SentimentAnalysisResult(BaseModel):
    """情緒面分析結果（SentimentAnalyst 輸出；TW only）。

    v1.1 新設：以「新聞情緒聚合」重建原版社群情緒分析師（本環境無社群爬蟲資料）。
    綜合個股新聞語氣 + 大盤新聞語氣 + 情緒分數（news_metadata.sentiment_score）
    推導市場情緒與討論熱度，明確與籌碼面（chip）、純新聞摘要（news）區隔。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=40, max_length=2000)
    market_sentiment: Literal["極度樂觀", "樂觀", "中性", "悲觀", "極度悲觀"]
    sentiment_score: Decimal = Field(
        ge=Decimal("-1"), le=Decimal("1"), description="綜合情緒分數（-1 極空 ~ +1 極多）"
    )
    buzz_level: Literal["高", "中", "低"] = Field(description="新聞討論熱度（近 7 日聲量）")
    momentum: Literal["轉強", "持平", "轉弱"] = Field(description="情緒相對前期的變化方向")
    key_drivers: list[str] = Field(min_length=0, max_length=6, description="推動情緒的關鍵題材")
    contrarian_flag: bool = Field(
        default=False, description="是否為極端情緒（過熱/過冷）可能反向的警示"
    )
    risk_factors: list[str] = Field(min_length=0, max_length=6, default_factory=list)
    confidence: int = Field(ge=0, le=100)

    @field_validator("sentiment_score", mode="before")
    @classmethod
    def _coerce_score(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int | float):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                return Decimal(v.strip())
            except Exception as e:
                raise ValueError(f"sentiment_score 無法轉 Decimal：{v!r}") from e
        raise ValueError(f"sentiment_score 不支援的 type: {type(v).__name__}")


# ── Researcher / Manager Schemas ────────────────────────


class BullArgument(BaseModel):
    """Bull researcher 單輪論點。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    points: list[str] = Field(min_length=3, max_length=8)
    confidence: int = Field(ge=0, le=100)
    evidence_from: list[Literal["market", "fundamental", "news", "sentiment", "chip"]] = Field(
        min_length=1,
        max_length=5,
    )


class BearArgument(BaseModel):
    """Bear researcher 單輪論點（同結構，不同立場）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    points: list[str] = Field(min_length=3, max_length=8)
    confidence: int = Field(ge=0, le=100)
    evidence_from: list[Literal["market", "fundamental", "news", "sentiment", "chip"]] = Field(
        min_length=1,
        max_length=5,
    )


class TraderProposal(BaseModel):
    """Trader 交易提案 — 把 ResearchManager 的研究計畫轉成具體交易主張。

    對應原版 tauricresearch/tradingagents 的 TraderProposal；TW 化為 3-level + 部位%。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["BUY", "HOLD", "SELL"]
    conviction: int = Field(ge=0, le=100, description="對此提案的把握度")
    suggested_position_pct: Decimal = Field(
        ge=Decimal("0"), le=Decimal("100"), description="建議部位（佔投組 %）"
    )
    rationale_zh: str = Field(min_length=80, max_length=1500)
    key_risks: list[str] = Field(min_length=1, max_length=6)

    @field_validator("suggested_position_pct", mode="before")
    @classmethod
    def _coerce_pct(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int | float):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                return Decimal(v.strip().rstrip("%"))
            except Exception as e:
                raise ValueError(f"suggested_position_pct 無法轉 Decimal：{v!r}") from e
        raise ValueError(f"suggested_position_pct 不支援的 type: {type(v).__name__}")


class RiskArgument(BaseModel):
    """風險辯論單輪論點（積極/保守/中立其一）。

    對應原版 risk_mgmt 的 aggressive/conservative/neutral debator；TW 化為結構化輸出，
    避免純自由文字辯論帶來的失真（每方需明確表態 stance_action + 證據點）。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    stance: Literal["aggressive", "conservative", "neutral"]
    stance_action: Literal["BUY", "HOLD", "SELL"]
    """此風險立場支持的動作（供 RiskManager / Verifier 計票）。"""
    points: list[str] = Field(min_length=2, max_length=6)
    confidence: int = Field(ge=0, le=100)


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
            try:
                return Decimal(v.strip().rstrip("%"))
            except Exception as e:
                # 統一轉成 ValueError 讓 pydantic 接住（含 decimal.InvalidOperation）
                raise ValueError(f"position_size_pct 無法轉為 Decimal：{v!r}") from e
        raise ValueError(f"position_size_pct 不支援的 type: {type(v).__name__}")

    @model_validator(mode="after")
    def _check_price_coherence(self) -> FinalSignal:
        """跨欄位驗證：價位邏輯需自洽。

        LLM 偶爾會吐出顛倒或方向錯誤的價位（如 BUY 卻把停損設在目標價之上、
        或 target_price_low > target_price_high）。這些不自洽訊號會直接被
        `signal_to_pending_order` 轉成 PendingOrder 等管理員核准——在此攔下，
        讓 `llm_call_with_schema` 的 repair retry 要求 LLM 修正。
        """
        low = self.target_price_low
        high = self.target_price_high
        sl = self.stop_loss

        # 1) 目標價區間：low 不可大於 high（防顛倒）
        if low is not None and high is not None and low > high:
            raise ValueError(f"target_price_low（{low}）不可大於 target_price_high（{high}）")

        # 2) 停損方向需與動作一致
        if self.action == "BUY" and sl is not None:
            ref = low if low is not None else high
            if ref is not None and sl >= ref:
                raise ValueError(f"BUY 訊號的 stop_loss（{sl}）應低於目標價（{ref}）")
        if self.action == "SELL" and sl is not None:
            ref = high if high is not None else low
            if ref is not None and sl <= ref:
                raise ValueError(f"SELL 訊號的 stop_loss（{sl}）應高於目標價（{ref}）")

        return self


# ── exports ────────────────────────────────────────────


__all__ = [
    "BearArgument",
    "BullArgument",
    "ChipAnalysisResult",
    "FinalSignal",
    "FundamentalAnalysisResult",
    "MarketAnalysisResult",
    "NewsAnalysisResult",
    "NewsSupportingArticle",
    "RiskArgument",
    "SentimentAnalysisResult",
    "TraderProposal",
]

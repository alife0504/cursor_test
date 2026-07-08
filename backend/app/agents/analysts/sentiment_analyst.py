"""SentimentAnalyst — 情緒面分析師（TW only，v1.1 新設）。

原版 tauric 的 sentiment 分析師吃社群媒體（Reddit）。本環境無社群爬蟲資料，
改以「新聞情緒聚合」重建：綜合個股新聞語氣 + 大盤新聞語氣 + 情緒分數
（news_metadata.sentiment / sentiment_score），推導市場情緒、討論熱度與動能。

與其他分析師的界線：
- 與 news（新聞摘要）區隔：sentiment 不做議題整理，只量化「情緒溫度與變化」。
- 與 chip（籌碼面）區隔：chip 看法人/融資券的資金流，sentiment 看輿論語氣。

降級策略：
- 完全無新聞（個股 + 大盤皆空）→ 回中性 stub 結果（confidence 低），不 raise、不炸圖。
"""

from __future__ import annotations

import time
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.schemas import SentimentAnalysisResult
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.errors import ValidationError
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)

# news_metadata.sentiment enum → 數值分數（供後端粗聚合，LLM 再據此細判）
_SENTIMENT_WORD_TO_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
    "unknown": 0.0,
}


@register_analyst
class SentimentAnalyst(BaseAnalyst):
    """情緒面分析師（台股 only）— 新聞情緒聚合。"""

    name: ClassVar[str] = "sentiment"
    display_name_zh: ClassVar[str] = "情緒面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW]
    required_data_kinds: ClassVar[list[DataKind]] = [DataKind.NEWS]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")

        if self.llm is None or self.tools is None:
            text = (
                f"[stub] {self.display_name_zh} 對 {symbol} 的情緒面分析。"
                "（無 LLM/tools 注入，回 framework stub）"
            )
            logger.info("analyst.sentiment.stub", symbol=symbol)
            return {"analyses": {self.name: text}}

        # Region 防呆（僅台股）
        if state.get("region", "TW") != "TW":
            raise ValidationError(
                message_zh="SentimentAnalyst 僅支援台股",
                symbol=symbol,
                region=state.get("region"),
            )

        company = await self.tools.get_company_info(symbol)

        # 近 7 日個股新聞 + 近 14 日大盤新聞（前 7 vs 後 7 用來看動能）
        stock_news = await self.tools.get_news(symbol, days_back=7, max_items=30)
        try:
            market_news = await self.tools.get_market_news(days_back=7, max_items=20, market="TWSE")
        except Exception as exc:
            logger.warning("sentiment.market_news_failed", symbol=symbol, error=str(exc))
            market_news = []

        # 完全無資料 → 中性 stub（不 raise，交由圖續跑其餘分析師）
        if not stock_news and not market_news:
            empty = SentimentAnalysisResult(
                summary=(
                    f"近 7 日內未檢索到與 {symbol} 相關的個股新聞，亦無台股大盤新聞可供情緒判讀。"
                    "資料量不足，無法形成有意義的情緒溫度，confidence 設為偏低。"
                    "建議結合技術面、基本面與籌碼面結論綜合判讀。"
                ),
                market_sentiment="中性",
                sentiment_score=Decimal("0"),
                buzz_level="低",
                momentum="持平",
                key_drivers=[],
                contrarian_flag=False,
                risk_factors=["情緒資料不足，判讀可靠度低"],
                confidence=20,
            )
            logger.info("sentiment_analyst.no_data", symbol=symbol)
            return {
                "analyses": {self.name: empty.model_dump_json()},
                "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0),
            }

        stock_agg = _aggregate_sentiment(stock_news)
        market_agg = _aggregate_sentiment(market_news)

        user_prompt = render_template(
            "sentiment_analyst_user_template",
            symbol=symbol,
            company_name=company.get("name") or symbol,
            industry=company.get("industry") or "未提供",
            stock_news_count=len(stock_news),
            stock_pos=stock_agg["pos"],
            stock_neu=stock_agg["neu"],
            stock_neg=stock_agg["neg"],
            stock_avg_score=_fmt_score(stock_agg["avg_score"]),
            market_news_count=len(market_news),
            market_pos=market_agg["pos"],
            market_neu=market_agg["neu"],
            market_neg=market_agg["neg"],
            market_avg_score=_fmt_score(market_agg["avg_score"]),
            stock_news_table=_format_news_table(stock_news),
            market_news_table=_format_news_table(market_news),
        )
        system_prompt = load_prompt("sentiment_analyst_system")

        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            SentimentAnalysisResult,
            model=resolve_agent_model(state, self.name),
            max_tokens=2048,
            temperature=0.4,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        if analysis_id:
            try:
                async with rw_session() as session:
                    await record_llm_usage(
                        session,
                        analysis_id=analysis_id,
                        user_id=state.get("user_id"),
                        provider=self.llm.name,
                        model=(
                            getattr(self.llm, "last_used_model", None)
                            or getattr(self.llm, "default_model", "unknown")
                        ),
                        usage=usage,
                        purpose="analyst.sentiment",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("sentiment_analyst.usage_record_failed", error=str(exc))

        logger.info(
            "analyst.sentiment.done",
            symbol=symbol,
            market_sentiment=result.market_sentiment,
            confidence=result.confidence,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        return {
            "analyses": {self.name: result.model_dump_json()},
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── 聚合 helpers ───────────────────────────────────────


def _aggregate_sentiment(news: list[dict[str, Any]]) -> dict[str, Any]:
    """統計一批新聞的情緒分布 + 平均分數。

    優先用 sentiment_score（-1~1 連續值）；缺則以 sentiment enum 映射粗分。
    """
    counter: Counter[str] = Counter()
    scores: list[float] = []
    for r in news:
        word = (r.get("sentiment") or "unknown").lower()
        counter[word] += 1
        raw_score = r.get("sentiment_score")
        val = _to_float(raw_score)
        if val is None:
            val = _SENTIMENT_WORD_TO_SCORE.get(word, 0.0)
        scores.append(val)
    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        "pos": counter.get("positive", 0),
        "neu": counter.get("neutral", 0) + counter.get("unknown", 0),
        "neg": counter.get("negative", 0),
        "avg_score": avg,
    }


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fmt_score(v: float) -> str:
    return f"{v:+.2f}"


def _format_news_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無相關新聞)"
    lines = ["| 標題 | 來源 | 發布時間 | sentiment | score |", "|---|---|---|---|---|"]
    for r in rows[:20]:
        title = (r.get("title") or "")[:100].replace("|", "/")
        score = r.get("sentiment_score")
        lines.append(
            f"| {title} | {r.get('source') or ''} | "
            f"{r.get('published_at') or ''} | {r.get('sentiment') or 'unknown'} | "
            f"{score if score is not None else '-'} |"
        )
    return "\n".join(lines)


__all__ = ["SentimentAnalyst"]

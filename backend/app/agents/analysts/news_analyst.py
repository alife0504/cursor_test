"""NewsAnalyst — 新聞/公告面分析師（TW + US）。

P13 完整版：
- 抓近 7 日新聞 metadata + 30 日重大公告。
- LLM 結構化輸出 NewsAnalysisResult。
- Qdrant similarity search 為「加分功能」：若 collection 有 vector 則做 top-K，
  否則退化為純 metadata 模式（不 raise）。
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.schemas import NewsAnalysisResult
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class NewsAnalyst(BaseAnalyst):
    """新聞/公告分析師。

    支援：TW + US
    依賴資料：NEWS + ANNOUNCEMENT
    """

    name: ClassVar[str] = "news"
    display_name_zh: ClassVar[str] = "新聞/公告分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW, MarketRegion.US]
    required_data_kinds: ClassVar[list[DataKind]] = [
        DataKind.NEWS,
        DataKind.ANNOUNCEMENT,
    ]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")
        region = (state.get("region") or "TW").upper()

        if self.llm is None or self.tools is None:
            text = (
                f"[stub] {self.display_name_zh} 對 {symbol} 的新聞分析。"
                "（無 LLM/tools 注入，回 framework stub）"
            )
            logger.info("analyst.news.stub", symbol=symbol)
            return {"analyses": {self.name: text}}

        company = await self.tools.get_company_info(symbol)
        news = await self.tools.get_news(symbol, days_back=7, max_items=20)
        try:
            announcements = await self.tools.get_announcements(symbol, days_back=30)
        except Exception as exc:
            logger.warning("news_analyst.announcements_failed", symbol=symbol, error=str(exc))
            announcements = []

        # 總經/大盤新聞（symbol=NULL 的市場層級新聞）— 原版 get_global_news 等價功能。
        # 失敗不擋（總經是加分脈絡，不是必要條件）。
        market_kind = "US" if region == "US" else "TWSE"
        try:
            macro_news = await self.tools.get_market_news(
                days_back=7, max_items=15, market=market_kind
            )
        except Exception as exc:
            logger.warning("news_analyst.macro_news_failed", symbol=symbol, error=str(exc))
            macro_news = []

        # 個股新聞、公告、總經新聞全空 → 回固定 neutral 結果（不 raise，prompt 上明確說可空）。
        if not news and not announcements and not macro_news:
            empty_result = NewsAnalysisResult(
                summary=(
                    f"近 7 日內未檢索到與 {symbol} 相關的新聞或公告，亦無大盤/總經新聞"
                    "（cnyes RSS / 公開資訊觀測站）。"
                    "資料量不足，無法做出有意義的情緒判斷，confidence 設為偏低。"
                    "建議使用者：1) 確認資料管線運作 2) 拉長觀察窗口 3) 結合其他分析師結論判讀。"
                ),
                sentiment="中性",
                key_topics=[],
                supporting_articles=[],
                impact_assessment="期間內無相關新聞，情緒中性。",
                macro_context="",
                macro_bias="未提供",
                confidence=20,
            )
            logger.info("news_analyst.no_data", symbol=symbol)
            return {
                "analyses": {self.name: empty_result.model_dump_json()},
                "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0),
            }

        # 渲染 prompt（依 region 切台股/美股；欄位 schema 完全相容）
        template_name = (
            "news_analyst_user_us_template" if region == "US" else "news_analyst_user_tw_template"
        )
        user_prompt = render_template(
            template_name,
            symbol=symbol,
            company_name=company.get("name") or symbol,
            industry=company.get("industry") or "未提供",
            news_count=len(news),
            news_table=_format_news_table(news),
            announcements_table=_format_ann_table(announcements),
            macro_news_count=len(macro_news),
            macro_news_table=_format_news_table(macro_news),
        )
        system_prompt = load_prompt("news_analyst_system")

        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            NewsAnalysisResult,
            model=resolve_agent_model(state, self.name),
            max_tokens=4096,  # 實測：本專案 schema(含中文 summary)+思考 token 需 ~2700，2048 會被截斷
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
                        purpose="analyst.news",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("news_analyst.usage_record_failed", error=str(exc))

        logger.info(
            "analyst.news.done",
            symbol=symbol,
            sentiment=result.sentiment,
            confidence=result.confidence,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        return {
            "analyses": {self.name: result.model_dump_json()},
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── helpers ────────────────────────────────────────────


def _format_news_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無相關新聞)"
    lines = ["| 標題 | 來源 | 發布時間 | URL | sentiment(metadata) |", "|---|---|---|---|---|"]
    for r in rows[:20]:
        title = (r.get("title") or "")[:120].replace("|", "/")
        lines.append(
            f"| {title} | {r.get('source') or ''} | "
            f"{r.get('published_at') or ''} | {r.get('url') or ''} | "
            f"{r.get('sentiment') or 'unknown'} |"
        )
    return "\n".join(lines)


def _format_ann_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無重大公告)"
    lines = ["| 類型 | 標題 | 發布時間 |", "|---|---|---|"]
    for r in rows[:15]:
        title = (r.get("title") or "")[:120].replace("|", "/")
        lines.append(
            f"| {r.get('announcement_type') or ''} | {title} | {r.get('published_at') or ''} |"
        )
    return "\n".join(lines)


__all__ = ["NewsAnalyst"]

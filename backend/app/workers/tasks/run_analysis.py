"""LangGraph 主分析任務 — `run_analysis(analysis_id, analyst_types, debate_rounds)`。

依 PLAN.md 第 14.7 / 14.8 章 worker + 第 14.9 章 State + 第 15.4 章 orphan cleanup。

P13 升級：
- 4 種 Analyst 從 stub 升級為真實 LLM call。
- ResearchManager 取代 placeholder_manager。
- 寫回 DB：signal + report_md + confidence + target_price + stop_loss + take_profit
  + llm_provider + llm_model + total_tokens + total_cost_usd（從 llm_usage 表彙總）。
- task kwargs 接受 analyst_types 與 debate_rounds（避開 analysis_reports 缺欄位）。

未來：
- P14：LLM Fallback Chain + WS streaming + 月配額。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import func, select

from app.agents.graph_builder import build_graph, build_initial_state
from app.agents.tools import ToolRegistry
from app.core.config import settings
from app.core.database import sync_rw_session
from app.llm import get_llm_provider
from app.llm.base_provider import BaseLLMProvider
from app.models.analysis import AnalysisReport
from app.models.quota import LLMUsage
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


# ════════════════ Task ════════════════


@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_analysis.run_analysis",
    time_limit=1200,
    soft_time_limit=900,
    max_retries=0,
)
def run_analysis(
    self: Any,
    analysis_id: str,
    analyst_types: list[str] | None = None,
    debate_rounds: int = 1,
) -> dict[str, Any]:
    """主分析任務。

    Args:
        analysis_id: analysis_reports.id（UUID 字串）。
        analyst_types: 要啟用的 Analyst 名稱清單；None / [] → graph 自動全選（依 region 過濾）。
        debate_rounds: Bull/Bear 辯論輪次（0 = 跳過）。
    """
    logger.info(
        "run_analysis.start analysis_id=%s types=%s rounds=%s",
        analysis_id,
        analyst_types,
        debate_rounds,
    )

    try:
        return _run_with_loop(analysis_id, analyst_types, debate_rounds)
    except Exception as exc:
        logger.exception("run_analysis.unhandled analysis_id=%s", analysis_id)
        _safe_mark_failed(analysis_id, str(exc))
        raise


def _run_with_loop(
    analysis_id: str,
    analyst_types: list[str] | None,
    debate_rounds: int,
) -> dict[str, Any]:
    """在新 event loop 中跑 async pipeline。"""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_pipeline(analysis_id, analyst_types, debate_rounds))
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for t in pending:
                t.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()
            asyncio.set_event_loop(None)


async def _async_pipeline(
    analysis_id: str,
    analyst_types: list[str] | None,
    debate_rounds: int,
) -> dict[str, Any]:
    started_at = datetime.now(tz=UTC)

    # 1. 取 DB row
    report_data = _fetch_pending_report(analysis_id)
    if report_data is None:
        raise RuntimeError(f"analysis_reports id={analysis_id} 不存在")

    _update_status(analysis_id, status="running", started_at=started_at)

    # 2. 拿 llm（必須有；若 init 失敗 → mark failed）
    llm: BaseLLMProvider
    try:
        llm = get_llm_provider(settings.LLM_DEFAULT_PROVIDER, settings)
    except Exception as exc:
        logger.exception("run_analysis.llm.init_failed")
        _safe_mark_failed(analysis_id, f"LLM init failed: {exc}")
        raise

    # 3. 建 tool registry + graph
    tools, tool_engine = _build_tool_registry()
    try:
        graph = build_graph(
            symbol=report_data["symbol"],
            market=report_data["market"],
            analyst_types=analyst_types or None,
            debate_rounds=int(debate_rounds),
            llm=llm,
            tools=tools,
        )

        initial = build_initial_state(
            symbol=report_data["symbol"],
            market=report_data["market"],
            analysis_id=analysis_id,
            trace_id=report_data.get("trace_id", "") or "",
            analyst_types=analyst_types,
            llm_model=report_data["llm_model"],
            debate_rounds=int(debate_rounds),
        )

        # recursion_limit 設大一點（多輪辯論可能多 hop）
        final_state = await graph.ainvoke(initial, config={"recursion_limit": 25})

        # 4. 寫回 DB
        duration_s = (datetime.now(tz=UTC) - started_at).total_seconds()
        signal_dict: dict[str, Any] = final_state.get("signal") or {}

        _update_completed(
            analysis_id=analysis_id,
            signal_dict=signal_dict,
            report_md=final_state.get("report_md"),
            llm_provider=getattr(llm, "name", None),
            llm_model=getattr(llm, "default_model", None),
            total_tokens=int(final_state.get("llm_usage_total_tokens", 0) or 0),
        )

        logger.info(
            "run_analysis.done analysis_id=%s duration=%.1fs action=%s confidence=%s",
            analysis_id,
            duration_s,
            signal_dict.get("action"),
            signal_dict.get("confidence"),
        )

        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "report_md_len": len(final_state.get("report_md") or ""),
            "tokens": int(final_state.get("llm_usage_total_tokens", 0) or 0),
            "duration_s": round(duration_s, 1),
            "action": signal_dict.get("action"),
        }
    finally:
        try:
            await tool_engine.dispose()
        except Exception as exc:  # pragma: no cover
            logger.warning("run_analysis.tool_engine.dispose_failed error=%s", exc)


# ════════════════ Helpers ════════════════


def _fetch_pending_report(analysis_id: str) -> dict[str, Any] | None:
    with sync_rw_session() as s:
        row = s.get(AnalysisReport, UUID(analysis_id))
        if row is None:
            return None
        return {
            "id": str(row.id),
            "symbol": row.symbol,
            "market": row.market,
            "status": row.status,
            "llm_model": row.llm_model or settings.LLM_DEFAULT_MODEL,
            "trace_id": "",
        }


def _update_status(
    analysis_id: str,
    *,
    status: str,
    started_at: datetime | None = None,
    error_msg: str | None = None,
) -> None:
    with sync_rw_session() as s:
        row = s.get(AnalysisReport, UUID(analysis_id))
        if row is None:
            logger.warning("run_analysis.update_status.row_missing id=%s", analysis_id)
            return
        row.status = status
        if started_at is not None:
            row.started_at = started_at
        if error_msg is not None:
            row.error_msg = error_msg[:8000]
        s.commit()


def _update_completed(
    *,
    analysis_id: str,
    signal_dict: dict[str, Any],
    report_md: str | None,
    llm_provider: str | None,
    llm_model: str | None,
    total_tokens: int,
) -> None:
    """寫回 completed 狀態 + signal 拆解 + 從 llm_usage 表彙總 cost。"""
    with sync_rw_session() as s:
        row = s.get(AnalysisReport, UUID(analysis_id))
        if row is None:
            logger.warning("run_analysis.update_completed.row_missing id=%s", analysis_id)
            return
        row.status = "completed"
        row.completed_at = datetime.now(tz=UTC)
        row.report_md = report_md or row.report_md
        row.llm_provider = llm_provider or row.llm_provider
        row.llm_model = llm_model or row.llm_model
        row.total_tokens = int(total_tokens)

        # signal 拆解
        action = signal_dict.get("action")
        confidence_raw = signal_dict.get("confidence")
        if isinstance(action, str) and action in ("BUY", "SELL", "HOLD"):
            row.signal = action
        if confidence_raw is not None:
            try:
                # FinalSignal 的 confidence 是 0~100 (int)，DB 欄位是 Numeric(5,4)（0~1.0）
                conf_int = int(confidence_raw)
                row.confidence = (Decimal(conf_int) / Decimal("100")).quantize(Decimal("0.0001"))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "run_analysis.confidence_parse_failed",
                    raw=confidence_raw,
                    error=str(exc),
                )

        # 價位
        row.target_price = _decimal_or_none(signal_dict.get("target_price_low"))
        # 取 high 作為 take_profit，low 作為 target_price 中位
        tp_high = _decimal_or_none(signal_dict.get("target_price_high"))
        if tp_high is not None:
            row.take_profit = tp_high
        row.stop_loss = _decimal_or_none(signal_dict.get("stop_loss"))

        # 彙總 cost = llm_usage WHERE analysis_id 的 sum
        cost_sum = s.execute(
            select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                LLMUsage.analysis_id == UUID(analysis_id)
            )
        ).scalar()
        row.total_cost_usd = Decimal(cost_sum or 0).quantize(Decimal("0.000001"))

        s.commit()


def _decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _safe_mark_failed(analysis_id: str, error: str) -> None:
    try:
        with sync_rw_session() as s:
            row = s.get(AnalysisReport, UUID(analysis_id))
            if row is None:
                return
            row.status = "failed"
            row.completed_at = datetime.now(tz=UTC)
            row.error_msg = error[:8000]
            s.commit()
    except Exception as exc:  # pragma: no cover
        logger.critical(
            "run_analysis.mark_failed.failed analysis_id=%s error=%s mark_error=%s",
            analysis_id,
            error,
            exc,
        )


def _build_tool_registry() -> tuple[ToolRegistry, Any]:
    """在 celery task 內建一份新的 async ro engine + sessionmaker → ToolRegistry。

    跨 task 不共用 engine（避免跨 event loop 衝突，PLAN 14.7 已知陷阱）。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(
        settings.postgres_dsn_ro,
        echo=False,
        pool_size=2,
        max_overflow=1,
        pool_pre_ping=True,
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)
    return ToolRegistry(sm), engine


# ── Redis pubsub helper（P14 streaming events 用）─────


def _publish_event(analysis_id: str, event: dict[str, Any]) -> None:
    try:
        import redis

        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD.get_secret_value(),
            db=0,
        )
        channel = f"analysis:{analysis_id}"
        client.publish(channel, json.dumps(event, ensure_ascii=False, default=str))
    except Exception as exc:  # pragma: no cover
        logger.warning("run_analysis.publish_event.failed error=%s", exc)


__all__ = ["run_analysis"]

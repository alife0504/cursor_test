"""LangGraph 主分析任務 — `run_analysis(analysis_id)`。

依 PLAN.md 第 14.7 / 14.8 章 worker + 第 14.9 章 State + 第 15.4 章 orphan cleanup。

⚠️ Phase 12 階段：
- 4 種 Analyst 都是 stub（回固定字串）
- LLM Provider 只接 Gemini（無 fallback）
- Bull/Bear/Manager 在 P13 才加入 graph
- 跑 2330 應 status=completed + report_md 為固定模板（不是真實 LLM 分析）

完整版時程：
- P13：4 種台股 Analyst 真實 prompt + Bull/Bear/Manager + 結構化輸出
- P14：美股 Analyst 共用 class + LLM Fallback Chain + WS streaming + 月配額

設計：
- bind=True 拿到 self；time_limit=1200s (hard) / soft=900s（PLAN 14.8）
- 失敗 → status='failed' + error_msg；最終 retry 失敗由 task_failure signal 寫 DLQ
- 並非 retry：LangGraph 邏輯錯誤不該無腦 retry（消耗 LLM cost）；只在明確的暫時錯誤 retry
- 在 celery 同步上下文中用 single event loop pattern（asyncio.new_event_loop + run_until_complete），
  避免反覆 asyncio.run() 在同一 process 重建 loop
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger

from app.agents.graph_builder import build_graph, build_initial_state
from app.agents.tools import ToolRegistry
from app.core.config import settings
from app.core.database import sync_rw_session
from app.llm import get_llm_provider
from app.llm.base_provider import BaseLLMProvider
from app.models.analysis import AnalysisReport
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


# ════════════════ Task ════════════════


@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_analysis.run_analysis",
    time_limit=1200,
    soft_time_limit=900,
    # 不要 autoretry：LangGraph 失敗多半是邏輯 / LLM quota 問題，retry 浪費錢
    max_retries=0,
)
def run_analysis(self: Any, analysis_id: str) -> dict[str, Any]:
    """主分析任務。

    Args:
        analysis_id: analysis_reports.id（UUID 字串）。

    Returns:
        {"analysis_id", "status", "report_md_len", "tokens", "duration_s"}。
    """
    logger.info("run_analysis.start analysis_id=%s", analysis_id)

    try:
        return _run_with_loop(analysis_id)
    except Exception as exc:
        # 任何例外 → 標記為 failed（避免 status 卡 running）
        logger.exception("run_analysis.unhandled analysis_id=%s", analysis_id)
        _safe_mark_failed(analysis_id, str(exc))
        raise


def _run_with_loop(analysis_id: str) -> dict[str, Any]:
    """在新 event loop 中跑 async pipeline。"""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_pipeline(analysis_id))
    finally:
        try:
            # 給未取消的 task 一個 chance 結束（避免 RuntimeWarning）
            pending = asyncio.all_tasks(loop)
            for t in pending:
                t.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()
            asyncio.set_event_loop(None)


async def _async_pipeline(analysis_id: str) -> dict[str, Any]:
    """async 主流程：取 DB → build graph → ainvoke → 寫回 DB。"""
    started_at = datetime.now(tz=UTC)

    # ── 1. 從 DB 取 analysis_reports row（同步 session 拿，避免 async ro/rw 衝突）
    report_data = _fetch_pending_report(analysis_id)
    if report_data is None:
        raise RuntimeError(f"analysis_reports id={analysis_id} 不存在")

    # 標記為 running
    _update_status(
        analysis_id,
        status="running",
        started_at=started_at,
    )

    # ── 2. 建 graph
    llm: BaseLLMProvider | None = None
    tools: ToolRegistry | None = None
    try:
        llm = get_llm_provider(settings.LLM_DEFAULT_PROVIDER, settings)
    except Exception as exc:
        logger.warning("run_analysis.llm.init_failed error=%s", exc)
        # P12 stub 不一定需要 LLM 可用（Analyst stub 不呼叫 LLM）；繼續跑

    # ToolRegistry 需要 ro_sessionmaker；celery 同步 task 中建一份新的 async engine
    tools = _build_tool_registry()

    graph = build_graph(
        symbol=report_data["symbol"],
        market=report_data["market"],
        analyst_types=report_data["analyst_types"],
        debate_rounds=report_data["debate_rounds"],
        llm=llm,
        tools=tools,
    )

    initial = build_initial_state(
        symbol=report_data["symbol"],
        market=report_data["market"],
        analysis_id=analysis_id,
        trace_id=report_data.get("trace_id", "") or "",
        analyst_types=report_data["analyst_types"],
        llm_model=report_data["llm_model"],
        debate_rounds=report_data["debate_rounds"],
    )

    # ── 3. 跑 graph
    final_state = await graph.ainvoke(initial)

    # ── 4. 寫回 DB
    duration_s = (datetime.now(tz=UTC) - started_at).total_seconds()
    signal = final_state.get("signal") or {}
    _update_status(
        analysis_id,
        status="completed",
        completed_at=datetime.now(tz=UTC),
        report_md=final_state.get("report_md"),
        signal=signal.get("action"),
        total_tokens=int(final_state.get("llm_usage_total_tokens", 0) or 0),
    )

    logger.info(
        "run_analysis.done analysis_id=%s duration=%.1fs",
        analysis_id,
        duration_s,
    )

    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "report_md_len": len(final_state.get("report_md") or ""),
        "tokens": int(final_state.get("llm_usage_total_tokens", 0) or 0),
        "duration_s": round(duration_s, 1),
    }


# ════════════════ Helpers（同步 DB 操作）════════════════


def _fetch_pending_report(analysis_id: str) -> dict[str, Any] | None:
    """從 DB 取 analysis_reports row（同步 session，celery context）。"""
    with sync_rw_session() as s:
        row = s.get(AnalysisReport, UUID(analysis_id))
        if row is None:
            return None
        # 取出後立即解構（避免 session close 後 lazy load）
        return {
            "id": str(row.id),
            "symbol": row.symbol,
            "market": row.market,
            "status": row.status,
            "llm_model": row.llm_model or settings.LLM_DEFAULT_MODEL,
            # P12 stub：先用簡單 default；P13 起改從 audit details / 額外欄位讀
            "analyst_types": _default_analyst_types(),
            "debate_rounds": 1,
            "trace_id": "",
        }


def _default_analyst_types() -> list[str]:
    """P12 stub：預設啟用全部 analyst（讓 graph 自己依 region 過濾）。"""
    return ["market", "fundamental", "news", "sentiment"]


def _update_status(
    analysis_id: str,
    *,
    status: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    report_md: str | None = None,
    signal: str | None = None,
    total_tokens: int | None = None,
    error_msg: str | None = None,
) -> None:
    """更新 analysis_reports（同步 session）。"""
    with sync_rw_session() as s:
        row = s.get(AnalysisReport, UUID(analysis_id))
        if row is None:
            logger.warning("run_analysis.update_status.row_missing id=%s", analysis_id)
            return
        row.status = status
        if started_at is not None:
            row.started_at = started_at
        if completed_at is not None:
            row.completed_at = completed_at
        if report_md is not None:
            row.report_md = report_md
        if signal is not None:
            row.signal = signal
        if total_tokens is not None:
            row.total_tokens = int(total_tokens)
        if error_msg is not None:
            row.error_msg = error_msg[:8000]  # 防超欄寬
        s.commit()


def _safe_mark_failed(analysis_id: str, error: str) -> None:
    """try/except 包裹的 failed marker（避免 task 雪上加霜炸再炸）。"""
    try:
        _update_status(
            analysis_id,
            status="failed",
            completed_at=datetime.now(tz=UTC),
            error_msg=error,
        )
    except Exception as exc:  # pragma: no cover
        logger.critical(
            "run_analysis.mark_failed.failed analysis_id=%s error=%s mark_error=%s",
            analysis_id,
            error,
            exc,
        )


def _build_tool_registry() -> ToolRegistry:
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
    return ToolRegistry(sm)


# ── Redis pubsub helper（P14 streaming events 用，P12 預留）─────


def _publish_event(analysis_id: str, event: dict[str, Any]) -> None:
    """publish 一則 event 到 `analysis:{id}` channel。P14 才會用上。"""
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

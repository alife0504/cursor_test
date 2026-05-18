"""LangGraph 主分析任務 — `run_analysis(analysis_id, analyst_types, debate_rounds)`。

依 PLAN.md 第 14.4 / 14.7 / 14.8 章 worker + 第 14.9 章 State + 第 15.4 章 orphan cleanup。

P14 升級：
- LLM Fallback Chain：用 `get_llm_chain(settings)` 取代 single provider，自動切備援。
- WS streaming：開頭 publish `started` / 結束 publish `completed` 或 `failed`（每個
  node 完成的 event 由 graph_builder 的 `_stream_wrap` 自動發出）。
- pending_order 自動建立：signal=BUY/SELL → `signal_to_pending_order` 建單。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import func, select

from app.agents.graph_builder import build_graph, build_initial_state
from app.agents.managers.orders_decision import signal_to_pending_order
from app.agents.streaming import (
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
    publish_event_sync,
)
from app.agents.tools import ToolRegistry
from app.core.config import settings
from app.core.database import sync_rw_session
from app.llm import get_llm_chain
from app.llm.fallback_chain import LLMFallbackChain
from app.models.analysis import AnalysisReport
from app.models.order import PendingOrder
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

    # P14：publish "started" event（fire-and-forget；失敗不擋）
    publish_event_sync(
        analysis_id,
        EVENT_STARTED,
        {
            "symbol": report_data["symbol"],
            "market": report_data["market"],
            "analyst_types": list(analyst_types or []),
            "debate_rounds": int(debate_rounds),
            "started_at": started_at.isoformat(),
        },
    )

    # 2. 建 LLM Fallback Chain（P14；取代 P12 single provider）
    chain: LLMFallbackChain
    try:
        chain = get_llm_chain(settings)
    except Exception as exc:
        logger.exception("run_analysis.llm_chain.init_failed")
        _safe_mark_failed(analysis_id, f"LLM chain init failed: {exc}")
        publish_event_sync(analysis_id, EVENT_FAILED, {"error": f"LLM chain init failed: {exc}"})
        raise

    # 3. 建 tool registry + graph
    tools, tool_engine = _build_tool_registry()
    try:
        graph = build_graph(
            symbol=report_data["symbol"],
            market=report_data["market"],
            analyst_types=analyst_types or None,
            debate_rounds=int(debate_rounds),
            llm=chain,
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
        try:
            final_state = await graph.ainvoke(initial, config={"recursion_limit": 25})
        except Exception as exc:
            logger.exception("run_analysis.graph.failed analysis_id=%s", analysis_id)
            _safe_mark_failed(analysis_id, f"graph failed: {exc}")
            publish_event_sync(analysis_id, EVENT_FAILED, {"error": str(exc)[:500]})
            raise

        # 4. 寫回 DB
        duration_s = (datetime.now(tz=UTC) - started_at).total_seconds()
        signal_dict: dict[str, Any] = final_state.get("signal") or {}

        # provider 取「最後一次成功的 provider」（fallback chain 可能切過）
        used_provider = getattr(chain, "last_used_provider", None) or getattr(
            chain, "primary", "google"
        )
        used_model = report_data["llm_model"]

        _update_completed(
            analysis_id=analysis_id,
            signal_dict=signal_dict,
            report_md=final_state.get("report_md"),
            llm_provider=used_provider,
            llm_model=used_model,
            total_tokens=int(final_state.get("llm_usage_total_tokens", 0) or 0),
        )

        # 5. P14：建 pending_order（signal=BUY/SELL）
        pending_order_id: str | None = None
        try:
            order = signal_to_pending_order(
                signal_dict,
                analysis_id=analysis_id,
                user_id=report_data["user_id"],
                symbol=report_data["symbol"],
                market=report_data["market"],
            )
            if order is not None:
                _persist_pending_order(order)
                pending_order_id = str(order.id)
        except Exception as exc:
            # pending_order 失敗不擋整個 analysis；只 log warning
            logger.warning(
                "run_analysis.pending_order.failed analysis_id=%s error=%s",
                analysis_id,
                exc,
            )

        # 6. publish "completed" event
        publish_event_sync(
            analysis_id,
            EVENT_COMPLETED,
            {
                "action": signal_dict.get("action"),
                "confidence": signal_dict.get("confidence"),
                "report_excerpt": (final_state.get("report_md") or "")[:500],
                "used_provider": used_provider,
                "duration_s": round(duration_s, 1),
                "tokens": int(final_state.get("llm_usage_total_tokens", 0) or 0),
                "pending_order_id": pending_order_id,
            },
        )

        # 6.5. P18: 通知用戶分析完成（fire-and-forget；dispatcher 失敗不擋）
        try:
            from app.notifications import NotifyEvent, NotifyLevel, get_dispatcher

            user_uuid = UUID(report_data["user_id"]) if report_data.get("user_id") else None
            if user_uuid is not None:
                action = signal_dict.get("action") or "HOLD"
                confidence = signal_dict.get("confidence")
                title = f"分析完成 — {report_data['symbol']} ({action})"
                body_lines = [
                    f"標的：{report_data['symbol']}（{report_data['market']}）",
                    f"建議：{action}" + (f"  信心：{confidence}" if confidence is not None else ""),
                    f"耗時：{round(duration_s, 1)}s",
                    f"使用模型：{used_provider} / {used_model}",
                ]
                if pending_order_id:
                    body_lines.append(f"已建立待核准訂單：{pending_order_id}")
                get_dispatcher().dispatch_sync(
                    NotifyEvent(
                        event_type="analysis.completed",
                        user_id=user_uuid,
                        title=title,
                        body="\n".join(body_lines),
                        level=NotifyLevel.SUCCESS,
                        metadata={"trace_id": analysis_id, "symbol": report_data["symbol"]},
                    )
                )
        except Exception as exc:
            logger.warning(
                "run_analysis.notify.dispatch_failed analysis_id=%s error=%s",
                analysis_id,
                exc,
            )

        logger.info(
            "run_analysis.done analysis_id=%s duration=%.1fs action=%s confidence=%s used=%s order=%s",
            analysis_id,
            duration_s,
            signal_dict.get("action"),
            signal_dict.get("confidence"),
            used_provider,
            pending_order_id,
        )

        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "report_md_len": len(final_state.get("report_md") or ""),
            "tokens": int(final_state.get("llm_usage_total_tokens", 0) or 0),
            "duration_s": round(duration_s, 1),
            "action": signal_dict.get("action"),
            "used_provider": used_provider,
            "pending_order_id": pending_order_id,
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
            "user_id": str(row.user_id),
            "symbol": row.symbol,
            "market": row.market,
            "status": row.status,
            "llm_model": row.llm_model or settings.LLM_DEFAULT_MODEL,
            "trace_id": "",
        }


def _persist_pending_order(order: PendingOrder) -> None:
    """寫入 pending_orders（sync session）。"""
    with sync_rw_session() as s:
        s.add(order)
        s.commit()


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


# Streaming publish 改走 app.agents.streaming.publish_event_sync（P14）


__all__ = ["run_analysis"]

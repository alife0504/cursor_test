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
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import func, select, text

from app.agents.analyst_outputs import build_analyst_outputs
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
from app.models.analysis import AnalysisReport, DebateMessage
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
    risk_rounds: int = 0,
    agent_models: dict[str, str] | None = None,
) -> dict[str, Any]:
    """主分析任務。

    Args:
        analysis_id: analysis_reports.id（UUID 字串）。
        analyst_types: 要啟用的 Analyst 名稱清單；None / [] → graph 自動全選（依 region 過濾）。
        debate_rounds: Bull/Bear 辯論輪次（0 = 跳過）。
        risk_rounds: 風險辯論輪次（0 = 關閉完整風險架構；>0 = 啟用 trader+風險團隊+verifier）。
    """
    logger.info(
        "run_analysis.start analysis_id=%s types=%s rounds=%s risk_rounds=%s",
        analysis_id,
        analyst_types,
        debate_rounds,
        risk_rounds,
    )

    try:
        return _run_with_loop(analysis_id, analyst_types, debate_rounds, risk_rounds, agent_models)
    except Exception as exc:
        logger.exception("run_analysis.unhandled analysis_id=%s", analysis_id)
        _safe_mark_failed(analysis_id, str(exc))
        raise


def _run_with_loop(
    analysis_id: str,
    analyst_types: list[str] | None,
    debate_rounds: int,
    risk_rounds: int = 0,
    agent_models: dict[str, str] | None = None,
) -> dict[str, Any]:
    """在新 event loop 中跑 async pipeline。"""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _async_pipeline(analysis_id, analyst_types, debate_rounds, risk_rounds, agent_models)
        )
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
    risk_rounds: int = 0,
    agent_models: dict[str, str] | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(tz=UTC)

    # 1. 取 DB row
    report_data = _fetch_pending_report(analysis_id)
    if report_data is None:
        raise RuntimeError(f"analysis_reports id={analysis_id} 不存在")

    # 狀態守衛（原子 queued→running）：celery 全域 acks_late+reject_on_worker_lost 下，
    # worker 被殺/OOM/redeploy 會把未 ack 的訊息重投 → 整段重跑（雙倍 LLM 成本＋重複下單）。
    # 僅當目前為 queued 才認領；已被先前執行認領/完成則直接跳過，換取「至多一次」語意。
    if not _claim_report_for_run(analysis_id, started_at):
        logger.warning(
            "run_analysis.skip_already_claimed analysis_id=%s status=%s",
            analysis_id,
            report_data.get("status"),
        )
        return {"skipped": True, "analysis_id": analysis_id, "reason": "already_claimed"}

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
            risk_rounds=int(risk_rounds),
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
            user_id=report_data["user_id"],
            agent_models=agent_models,
        )

        # 完整架構：注入決策記憶（past_context）；僅風險層啟用時，且失敗不阻塞
        if int(risk_rounds) > 0:
            try:
                from app.agents.memory import AgentMemory

                initial["past_context"] = await AgentMemory().retrieve(
                    symbol=report_data["symbol"],
                    region="",
                    situation=f"標的 {report_data['symbol']}（{report_data['market']}）投資決策",
                )
            except Exception as exc:
                logger.warning("run_analysis.memory.retrieve_failed error=%s", exc)

        # recursion_limit 設大一點（多輪辯論可能多 hop）
        try:
            # recursion_limit 提高（完整風險架構多輪辯論 → 更多 hop）
            final_state = await graph.ainvoke(initial, config={"recursion_limit": 50})
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
        # 回報「實際使用的模型」而非「請求的模型」：若使用者選了缺金鑰的 provider，
        # chain 會 fallback 到可用 provider 的預設模型 —— 誠實顯示真正跑的模型，避免誤導。
        used_model = getattr(chain, "last_used_model", None) or report_data["llm_model"]

        _update_completed(
            analysis_id=analysis_id,
            signal_dict=signal_dict,
            report_md=final_state.get("report_md"),
            llm_provider=used_provider,
            llm_model=used_model,
            total_tokens=int(final_state.get("llm_usage_total_tokens", 0) or 0),
            analyses=final_state.get("analyses") or {},
        )

        # 4b. 把多空辯論歷程寫入 debate_history 表（前端「辯論詳情」分頁 + StatusStepper
        # 多空辯論階段 + Agent Flow reload 退路皆依賴此資料）。失敗不擋整次分析。
        try:
            _persist_debate_history(
                analysis_id,
                final_state.get("debate_history") or [],
                signal_dict=signal_dict,
                debate_rounds=int(debate_rounds),
            )
        except Exception as exc:  # pragma: no cover - 防禦性
            logger.warning(
                "run_analysis.persist_debate.failed analysis_id=%s error=%s",
                analysis_id,
                exc,
            )

        # 完整架構：把本次決策寫進記憶（供未來 past_context）；僅風險層、失敗不阻塞
        if int(risk_rounds) > 0 and signal_dict:
            try:
                from app.agents.memory import AgentMemory, build_situation_text

                await AgentMemory().store(
                    symbol=report_data["symbol"],
                    region="",
                    situation=build_situation_text(
                        report_data["symbol"], final_state.get("analyses") or {}
                    ),
                    decision=signal_dict,
                    analysis_id=analysis_id,
                )
            except Exception as exc:
                logger.warning("run_analysis.memory.store_failed error=%s", exc)

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
                # 直接 await async dispatch：本函式已在 worker 的 running event loop 內，
                # 用 dispatch_sync（內部 asyncio.run）會丟 RuntimeError 被吞掉→通知永遠沒送出。
                await get_dispatcher().dispatch(
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


def _claim_report_for_run(analysis_id: str, started_at: datetime) -> bool:
    """原子地把 analysis_reports 認領為 running（狀態守衛）。

    可認領的來源狀態：
    - 'queued'（正常首次執行）。
    - 'failed' 且 error_msg 帶 cleanup 的「stuck in queued」sentinel——批次忙碌時 worker 尚未輪到、
      卻被每小時 orphan cleanup 依 queued 逾時「暫時」標 failed 的項目。worker 一旦輪到就把它救回、
      清掉誤導的 error_msg（避免第一輪 claim 守衛 + queued cleanup 交互造成的靜默掉單）。
    回傳 False 代表已被其他執行認領/完成（或真正失敗且非上述 sentinel），呼叫端應跳過本次執行。
    """
    with sync_rw_session() as s:
        result = s.execute(
            text(
                """
                UPDATE analysis_reports
                   SET status = 'running',
                       started_at = :started_at,
                       error_msg = NULL,
                       updated_at = NOW()
                 WHERE id = :id
                   AND (status = 'queued'
                        OR (status = 'failed'
                            AND error_msg LIKE '%cleanup_orphans: stuck in queued%'))
                """
            ),
            {"id": UUID(analysis_id), "started_at": started_at},
        )
        s.commit()
        return (result.rowcount or 0) > 0


def _persist_pending_order(order: PendingOrder) -> None:
    """寫入 pending_orders（sync session）。

    重複下單防護：若同一 analysis_id 已存在 PENDING 委託則跳過（配合狀態守衛，
    避免任務重投時對同一分析建立第二筆待核准下單）。
    """
    with sync_rw_session() as s:
        existing = s.execute(
            select(func.count())
            .select_from(PendingOrder)
            .where(
                PendingOrder.analysis_id == order.analysis_id,
                PendingOrder.status == "PENDING",
            )
        ).scalar()
        if existing and int(existing) > 0:
            logger.warning(
                "run_analysis.pending_order.duplicate_skipped analysis_id=%s",
                str(order.analysis_id),
            )
            return
        s.add(order)
        s.commit()


def _persist_debate_history(
    analysis_id: str,
    debate_history: list[dict[str, Any]],
    *,
    signal_dict: dict[str, Any] | None = None,
    debate_rounds: int = 0,
) -> None:
    """把 LangGraph 產出的 debate_history 逐筆寫入 debate_history 表。

    debate_history 每筆為 {role, round, content(JSON字串或 dict), tokens?}。content 欄位是
    JSONB（DebateMessageOut 契約要求 dict/list），故 JSON 字串會被 parse；parse 失敗則以
    {"text": ...} 包裝。額外補一則 role='manager' 訊息（研究經理的最終 signal），供前端辯論
    分頁與 StatusStepper「多空辯論→經理」階段偵測。
    """
    rows: list[DebateMessage] = []
    max_round = 0
    for entry in debate_history:
        role = str(entry.get("role") or "unknown")
        round_num = int(entry.get("round") or 0)
        max_round = max(max_round, round_num)
        rows.append(
            DebateMessage(
                analysis_id=UUID(analysis_id),
                round_num=round_num,
                role=role,
                content=_coerce_debate_content(entry.get("content")),
                tokens_used=(int(entry["tokens"]) if entry.get("tokens") is not None else None),
            )
        )

    # 研究經理最終決策（signal）作為 manager 訊息，掛在「最後一個真實辯論輪」（max_round），
    # 讓前端 DebateTimeline 以該輪的結論卡呈現、與 bull/bear 同組——而非放到 max+1 造出一個
    # bull/bear 皆「（尚無）」的幻影空輪。debate_rounds=0（無多空辯論）時退回第 1 輪。
    if signal_dict:
        rows.append(
            DebateMessage(
                analysis_id=UUID(analysis_id),
                round_num=max_round if max_round > 0 else 1,
                role="manager",
                content=dict(signal_dict),
                tokens_used=None,
            )
        )

    if not rows:
        return
    with sync_rw_session() as s:
        s.add_all(rows)
        s.commit()


def _coerce_debate_content(content: Any) -> dict[str, Any] | list[Any]:
    """把 debate content 正規化成 JSONB 可存、DebateMessageOut 可回的 dict/list。"""
    if isinstance(content, (dict, list)):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (ValueError, TypeError):
            pass
        return {"text": content}
    return {"text": str(content) if content is not None else ""}


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
    analyses: dict[str, Any] | None = None,
) -> None:
    """寫回 completed 狀態 + signal 拆解 + analyst_outputs + 從 llm_usage 表彙總 cost。"""
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

        # v1.0.2：把各 analyst 結構化輸出寫進 analyst_outputs（前端 AnalystResultCard 用）
        analyst_outputs = build_analyst_outputs(analyses)
        if analyst_outputs:
            row.analyst_outputs = analyst_outputs
            # analyst_types 建立時若為空（auto-select），用實際跑過的 analyst 回填
            if not row.analyst_types:
                row.analyst_types = list(analyst_outputs.keys())

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

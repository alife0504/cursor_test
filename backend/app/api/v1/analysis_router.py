"""Phase 11 — /api/v1/analysis/* router。

POST 帶 Idempotency-Key（必選）；其他都需登入。
DELETE 僅 admin。

注意：run_analysis 是 stub（celery enqueue 在 P12+ 才接）。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.dependencies import admin_only, get_current_user
from app.core.cursor import Cursor, build_page_response, clamp_limit
from app.core.database import get_rw_session
from app.core.errors import QuotaExceededError, RateLimitError, ValidationError
from app.core.idempotency import IdempotencyService, compute_request_hash
from app.core.rate_limit import make_user_rate_limit_dependency
from app.core.response_envelope import envelope_success
from app.core.validators import validate_uuid
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisDetail,
    AnalysisSummary,
    DebateMessageOut,
)
from app.services.analysis_service import AnalysisService
from app.services.quota_service import QuotaService

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


def _dispatcher(request: Request):
    return getattr(request.app.state, "dispatcher", None)


def _get_service(request: Request, session: AsyncSession) -> AnalysisService:
    return AnalysisService(session, dispatcher=_dispatcher(request))


_TW_ONLY_ANALYSTS = {"sentiment", "chip"}


def _analysts_for_region(analyst_types: list[str], region: str) -> list[str]:
    """自動選股（批次）時，依市場過濾分析師。

    美股不支援台股專屬的情緒面 / 籌碼面；濾掉後若空則退回通用三面（技術/基本/新聞）。
    """
    if region.upper() != "US":
        return list(analyst_types)
    filtered = [a for a in analyst_types if a not in _TW_ONLY_ANALYSTS]
    return filtered or ["market", "fundamental", "news"]


def _enqueue_run_analysis(
    analysis_id: str,
    *,
    analyst_types: list[str] | None = None,
    debate_rounds: int = 1,
    risk_rounds: int = 0,
    agent_models: dict[str, str] | None = None,
) -> None:
    """推 celery task；任何 enqueue 錯誤（如 redis 不可用）不應炸 router。

    - DB 已寫入 status='queued'，task 失敗交給 orphan cleanup（PLAN 15.4）。
    - 測試環境 / CELERY_TASK_ALWAYS_EAGER → 直接 inline 跑，方便整合測試。
    - P13：analyst_types / debate_rounds 透過 task kwargs 傳遞
      （DB 模型未存這兩欄位，audit_logs 讀取脆弱）。
    """
    try:
        from app.workers.tasks.run_analysis import run_analysis as run_analysis_task

        kwargs: dict[str, object] = {
            "debate_rounds": int(debate_rounds),
            "risk_rounds": int(risk_rounds),
        }
        if analyst_types is not None:
            kwargs["analyst_types"] = list(analyst_types)
        if agent_models:
            kwargs["agent_models"] = dict(agent_models)
        run_analysis_task.apply_async(args=[analysis_id], kwargs=kwargs)
    except Exception:  # pragma: no cover - broker 不可用是 ops 問題
        # 不 re-raise；status=queued + orphan cleanup 兜底
        import logging

        logging.getLogger(__name__).exception(
            "analysis.enqueue.failed", extra={"analysis_id": analysis_id}
        )


# ════════════════ GET /llm-providers ════════════════
# 註：須在 GET /{analysis_id} 之前註冊，否則 "llm-providers" 會被當成 analysis_id。


@router.get("/llm-providers")
async def get_llm_providers(
    request: Request,
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """回報目前可用（已配置金鑰）的 LLM provider 與預設模型。

    前端據此標示／禁用無金鑰的模型選項，避免選了 GPT/Claude 卻被靜默降級為 Gemini。
    """
    from app.core.config import settings
    from app.llm import available_providers

    data = {
        "available_providers": available_providers(settings),
        "default_provider": settings.LLM_DEFAULT_PROVIDER,
        "default_model": settings.LLM_DEFAULT_MODEL,
    }
    return JSONResponse(
        status_code=200,
        content=envelope_success(data, trace_id=_trace_id(request)),
    )


# ════════════════ POST / ════════════════


@router.post(
    "",
    status_code=201,
    summary="建立新分析（Idempotency-Key required）",
    dependencies=[Depends(make_user_rate_limit_dependency())],  # L4：單一使用者 60/min（fail-open）
)
async def create_analysis(
    payload: AnalysisCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    if not idempotency_key:
        raise ValidationError(
            message_zh="缺少 Idempotency-Key header（POST /analysis 必須提供）",
            field="Idempotency-Key",
        )

    body_bytes = json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    req_hash = compute_request_hash("POST", "/api/v1/analysis", body_bytes)

    idem = IdempotencyService(session)
    existing = await idem.check_existing(
        key=idempotency_key,
        user_id=user.id,
        request_hash=req_hash,
    )
    if existing is not None:
        # Idempotent replay → 不重複扣 quota（response 已 cache）
        return JSONResponse(
            status_code=200,
            content=envelope_success(existing.response, trace_id=_trace_id(request)),
        )

    # PLAN 19.3 L5：每使用者分析建立 10/hr（在 replay 之後 → replay 不扣次數）。
    # 配額檢查（L6）有 TOCTOU：突發大量建立會全數通過（usage 尚未入帳），
    # L5 是把「單一時窗可燒掉的 LLM 成本」綁上限的第一道防線。fail-open（Redis 掛不擋）。
    from app.core.rate_limit import L5_ANALYSIS, RateLimiter
    from app.core.redis_client import RedisDB, get_redis

    _rl_redis = await get_redis(RedisDB.RATELIMIT)
    _rl = await RateLimiter(_rl_redis).check(
        f"{L5_ANALYSIS.key_prefix}{user.id}",
        limit=L5_ANALYSIS.limit,
        window_sec=L5_ANALYSIS.window_sec,
    )
    if not _rl.allowed:
        raise RateLimitError(
            message_zh=(
                f"分析建立頻率過高（每小時限 {L5_ANALYSIS.limit} 次），"
                f"請 {_rl.retry_after_sec} 秒後再試"
            ),
            retry_after_sec=_rl.retry_after_sec,
        )

    # P14：月配額檢查（在 idempotency 之後，避免 replay 也擋）
    # PYTEST_RUNNING 不跳過：integration test 需驗證 402；單測直接 mock service。
    # 用 router 注入的 session 避免跨 event loop 開新 pool。
    quota = QuotaService()
    allowed, used, limit = await quota.check_user_can_analyze(user.id, session=session)
    if not allowed:
        raise QuotaExceededError(
            message_zh=f"本月 LLM 預算已用完（{used} / {limit} USD）",
            used_usd=str(used),
            limit_usd=str(limit),
        )

    service = _get_service(request, session)
    trace_id = _trace_id(request)

    # 決定要分析的股票清單：
    #   - 指定個股（payload.symbol）→ 單筆（原行為）
    #   - 自動選股（payload.screen_level）→ 後端依等級批次篩選（純數據、不呼叫 LLM）
    screened_count = 0
    if payload.symbol:
        symbols: list[str] = [payload.symbol]
        effective_analysts = list(payload.analyst_types)
        is_batch = False
    else:
        from app.core.config import settings as _settings
        from app.services.screening_service import ScreeningService

        region = payload.market or "TW"
        candidates = await ScreeningService(session).select_symbols(
            region, payload.screen_level or "high"
        )
        screened = [c.symbol for c in candidates]
        if not screened:
            raise ValidationError(
                message_zh="自動選股：目前市場無符合條件的股票，請改為指定個股或稍後再試",
                field="screen_level",
            )
        screened_count = len(screened)
        # ⚠️ 硬上限：篩出的候選可能多達數百檔，但一次全跑完整分析成本/時間巨大、
        # 會爆月配額，故只實際建立排序後前 N 檔的分析（其餘為候選、未分析）。
        symbols = screened[: max(1, _settings.SCREEN_MAX_ANALYSES)]
        # 美股不支援台股專屬分析師（情緒 / 籌碼）→ 後端自我保護過濾
        effective_analysts = _analysts_for_region(payload.analyst_types, region)
        is_batch = True

    # P12：service commit 後才推 celery task。
    # P13：analyst_types + debate_rounds 透過 task kwargs 傳（DB 未存這兩欄位）。
    reports = []
    for sym in symbols:
        report = await service.create_analysis(
            user=user,
            symbol=sym,
            analyst_types=effective_analysts,
            llm_model=payload.llm_model,
            debate_rounds=payload.debate_rounds,
            risk_tolerance=payload.risk_tolerance,
            request_id=trace_id,
        )
        _enqueue_run_analysis(
            str(report.id),
            analyst_types=list(effective_analysts),
            debate_rounds=int(payload.debate_rounds),
            risk_rounds=int(payload.risk_rounds),
            agent_models=payload.agent_models,
        )
        reports.append(report)

    first = reports[0]
    body = AnalysisCreateResponse(
        analysis_id=first.id,
        status=first.status,
        estimated_seconds=180,
        count=len(reports),
        analysis_ids=[r.id for r in reports],
        screened_symbols=list(symbols) if is_batch else [],
        screened_count=screened_count,
    ).model_dump(mode="json")

    await idem.record_response(
        key=idempotency_key,
        user_id=user.id,
        request_hash=req_hash,
        status_code=201,
        response=body,
    )
    return envelope_success(body, trace_id=_trace_id(request))


# ════════════════ GET / list ════════════════


@router.get("", summary="列出分析（cursor 分頁）")
async def list_analysis(
    request: Request,
    status: str | None = Query(default=None, max_length=20),
    symbol: str | None = Query(default=None, max_length=20),
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = _get_service(request, session)
    limit = clamp_limit(limit)
    before_created_at = None
    if cursor:
        kwargs = Cursor.decode(cursor)
        before_created_at = kwargs.get("before_created_at")

    rows = await service.list_for_user(
        user,
        status=status,
        symbol=symbol,
        limit=limit + 1,
        before_created_at=before_created_at,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [AnalysisSummary.model_validate(r).model_dump(mode="json") for r in rows]
    next_kwargs = None
    if has_more and rows:
        next_kwargs = {"before_created_at": rows[-1].created_at}
    pagination = build_page_response(items, limit=limit, next_cursor_kwargs=next_kwargs)
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


# ════════════════ GET /{id} ════════════════


@router.get("/{analysis_id}", summary="取得分析詳情")
async def get_analysis(
    analysis_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = _get_service(request, session)
    uid = validate_uuid(analysis_id)
    report = await service.get_for_user(user, uid)
    return envelope_success(
        AnalysisDetail.model_validate(report).model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


# ════════════════ GET /{id}/debate ════════════════


@router.get("/{analysis_id}/debate", summary="取得 debate 過程")
async def get_debate(
    analysis_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = _get_service(request, session)
    uid = validate_uuid(analysis_id)
    msgs = await service.get_debate(user, uid)
    items = [DebateMessageOut.model_validate(m).model_dump(mode="json") for m in msgs]
    return envelope_success(items, trace_id=_trace_id(request))


# ════════════════ POST /{id}/cancel ════════════════


@router.post("/{analysis_id}/cancel", summary="取消分析")
async def cancel_analysis(
    analysis_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = _get_service(request, session)
    uid = validate_uuid(analysis_id)
    report = await service.cancel(user, uid, request_id=_trace_id(request))
    return envelope_success(
        {"analysis_id": str(report.id), "status": "cancelled"},
        trace_id=_trace_id(request),
    )


# ════════════════ DELETE /{id}（admin only）════════════════


@router.delete("/{analysis_id}", summary="刪除分析（admin only）")
async def delete_analysis(
    analysis_id: str,
    request: Request,
    admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = _get_service(request, session)
    uid = validate_uuid(analysis_id)
    await service.delete(admin, uid, request_id=_trace_id(request))
    return envelope_success(
        {"analysis_id": analysis_id, "deleted": True},
        trace_id=_trace_id(request),
    )


__all__ = ["router"]

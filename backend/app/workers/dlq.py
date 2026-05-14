"""Celery Dead Letter Queue（PLAN 第 14.10 章）。

`task_failure` signal 在 retry **全部用完後** 才 fire（celery default：retry 期間
fire 的是 `task_retry`，不是 `task_failure`），因此不會誤把暫時失敗寫入 DLQ。

DLQ 寫入失敗 → fallback 寫 file（避免無聲）。
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import signals

from app.core.database import sync_rw_session
from app.core.logging_config import get_logger
from app.models.dlq import CeleryDeadLetter

logger = get_logger(__name__)

# 寫 DB 失敗的 fallback 檔（避免完全無聲）
_FALLBACK_FILE = Path(
    os.environ.get("CELERY_DLQ_FALLBACK_FILE", "/tmp/celery_dlq_fallback.jsonl")  # noqa: S108
)

# JSON 序列化的 size 上限（args/kwargs 太大就截斷）
_MAX_JSON_BYTES = 64 * 1024
_MAX_TRACEBACK_LEN = 10_000


def _safe_json(value: Any) -> Any:
    """嘗試把 args/kwargs 轉成可 JSONB 的形態；失敗就 stringify。"""
    if value is None:
        return None
    try:
        # 先 round-trip 一次確認 JSON-able；超過 size 直接 truncate
        s = json.dumps(value, default=str, ensure_ascii=False)
        if len(s.encode("utf-8")) > _MAX_JSON_BYTES:
            return {"_truncated": True, "preview": s[:1024]}
        return json.loads(s)
    except (TypeError, ValueError):
        return {"_unserializable": str(value)[:1024]}


def _write_fallback(record: dict[str, Any]) -> None:
    """DB 寫不進去時的退路：append 一行 JSON 到 fallback 檔。"""
    try:
        _FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _FALLBACK_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        # 連 fallback 都失敗 → 至少 log critical
        logger.critical(
            "dlq.fallback_file_failed",
            error=str(exc),
            record_task=record.get("task_name"),
        )


@signals.task_failure.connect
def write_to_dlq(
    sender: Any = None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    args: Any = None,
    kwargs: Any = None,
    traceback: Any = None,
    einfo: Any = None,
    **_extra: Any,
) -> None:
    """task_failure signal handler — 把 final failure 寫入 celery_dead_letters。

    注意：retry 期間（self.retry()）不會 fire 這個 signal。只有真的最終失敗
    （retry 用完或非 retry-able exception）才會走到這裡。
    """
    task_name = getattr(sender, "name", "<unknown>") if sender is not None else "<unknown>"

    # einfo.traceback 比 traceback 參數更乾淨
    tb_str = ""
    if einfo is not None and hasattr(einfo, "traceback"):
        tb_str = str(einfo.traceback)
    elif traceback is not None:
        tb_str = str(traceback)
    if len(tb_str) > _MAX_TRACEBACK_LEN:
        tb_str = tb_str[: _MAX_TRACEBACK_LEN - 100] + "\n...[truncated]"

    exc_str = str(exception) if exception is not None else "<no exception>"
    exc_type = type(exception).__name__ if exception is not None else None

    # retry_count：celery 把 request 掛在 sender.request 上
    retry_count = 0
    request = getattr(sender, "request", None) if sender is not None else None
    if request is not None:
        retry_count = int(getattr(request, "retries", 0) or 0)

    # task_id 必須能塞進 UUID 欄位（dlq.task_id 是 UUID）。celery 預設給 UUID-like
    # 字串，但測試時可能丟其他字串 → 不能 parse 就丟 None
    parsed_task_id = None
    if task_id is not None:
        try:
            import uuid

            parsed_task_id = uuid.UUID(str(task_id))
        except ValueError:
            parsed_task_id = None

    record_for_fallback = {
        "task_name": task_name,
        "task_id": str(task_id) if task_id is not None else None,
        "exception_type": exc_type,
        "exception": exc_str,
        "retry_count": retry_count,
        "failed_at": datetime.now(UTC).isoformat(),
    }

    try:
        with sync_rw_session() as session:
            row = CeleryDeadLetter(
                task_name=task_name[:255],
                task_id=parsed_task_id,
                args=_safe_json(args),
                kwargs=_safe_json(kwargs),
                exception_type=exc_type[:255] if exc_type else None,
                exception=exc_str[:10_000],
                traceback=tb_str,
                retry_count=retry_count,
                resolved=False,
            )
            session.add(row)
            session.commit()
        logger.critical(
            "dlq.task_failed",
            task_name=task_name,
            task_id=str(task_id) if task_id else None,
            exception_type=exc_type,
            retry_count=retry_count,
        )
    except Exception as db_exc:
        logger.critical(
            "dlq.db_write_failed",
            task_name=task_name,
            task_id=str(task_id) if task_id else None,
            error=str(db_exc),
        )
        _write_fallback({**record_for_fallback, "db_write_error": str(db_exc)})


__all__ = ["write_to_dlq"]

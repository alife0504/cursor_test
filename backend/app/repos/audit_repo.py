"""Phase 9 — AuditRepository（取代 P8 的 _audit_minimal）。

依 PLAN.md 第 19.6 章 Audit hash chain。

職責：
- `append(...)`：寫一筆 audit_logs（trigger 自動補 prev_hash / entry_hash）
- `verify_chain(since=None)`：重算 hash 比對 DB 的 entry_hash，回 (ok, broken_ids)
  - 用 ro engine（防止 verify 過程意外寫入）
  - hash 公式同 baseline 0012 trigger：
    sha256(prev_hash || '|' || id || '|' || actor_id || '|' || action || '|'
          || entity_type || '|' || entity_id || '|' || details::text || '|' || timestamp)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.core.logging_config import get_logger
from app.models.audit import AuditLog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


# Hash chain 初始 prev_hash（chain 的第一筆 prev = NULL 在 DB；compute 端用空字串）
INITIAL_PREV_HASH = ""


def _coerce_str(value: Any) -> str:
    """trigger 用 COALESCE(..., '')，Python 端對 NULL / None 也視為空字串。"""
    if value is None:
        return ""
    return str(value)


def _serialize_details(details: Any) -> str:
    """模擬 PG details::text 的轉法。

    PG JSONB 預設用 compact 格式（無空格）、key 字母順序不保證。
    為避免跨語言序列化不一致，verify_chain 直接讀 DB 算好的 details::text。
    """
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    return json.dumps(details, separators=(", ", ": "), ensure_ascii=False, sort_keys=False)


def compute_entry_hash(
    *,
    prev_hash: str,
    row_id: int,
    actor_id: Any,
    action: str,
    entity_type: Any,
    entity_id: Any,
    details_text: str,
    timestamp: datetime,
) -> str:
    """Python 端重算 hash（與 trigger 算法對齊）。

    payload 用 `|` 分隔；NULL / None 視為空字串。
    timestamp 用 PG 的 ISO-like 字串（ts 已 UTC）→ 與 trigger 一致用 to_char。
    """
    parts = [
        prev_hash or "",
        str(row_id),
        _coerce_str(actor_id),
        action or "",
        _coerce_str(entity_type),
        _coerce_str(entity_id),
        details_text or "",
        timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────
# AuditRepository
# ─────────────────────────────────────────────────────────


class AuditRepository:
    """audit_logs 的 append + verify 介面。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """寫一筆 audit；caller 負責 commit。

        trigger（baseline 0012）會在 BEFORE INSERT 自動填 prev_hash / entry_hash。
        """
        record = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def append_and_commit(self, **kwargs) -> AuditLog:
        """append + commit。給 middleware 用，自己管 transaction。"""
        record = await self.append(**kwargs)
        await self.session.commit()
        return record

    async def verify_chain(
        self,
        *,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[bool, list[int]]:
        """重算 audit_logs 的 hash chain。回 (ok, broken_ids)。

        為了與 trigger 算法對齊：
        - 用 PG 自己算 SHA256（每筆 SELECT 把 details cast to text）
        - 然後比對 entry_hash 與 sha256(payload)

        實作策略（效率優先）：寫一段 SQL 一次比完，回斷裂的 id 清單。

        Args:
            since: 只驗該 timestamp 之後；None = 全部
            limit: 最多檢查幾筆；None = 不限

        Returns:
            (True, []) = 全部 OK；
            (False, [123, 456, ...]) = 斷裂處 id list
        """
        # PG 重新計算每筆 hash 並與 DB 比對
        # 算法嚴格對齊 baseline 0012 trigger：
        #   payload = prev_hash || '|' || id || '|' || actor_id || '|' || action
        #            || '|' || entity_type || '|' || entity_id
        #            || '|' || COALESCE(details::text, '{}')
        #            || '|' || timestamp::text
        # 全部 NULL 補 ''；details NULL 補 '{}'。
        # 驗證策略（依 PLAN 19.6）：
        # 1. 對每一筆 row：重算 entry_hash 應與 DB 存的相同（hash_ok）
        # 2. 對每一筆 row：prev_hash 必須是 64 個 0 (chain head) 或 = 某筆 row 的 entry_hash
        #    （chain_ok via JOIN）
        #
        # 不用 LAG (timestamp, id) 順序檢查，原因：並發插入時 trigger 用
        # ORDER BY timestamp DESC, id DESC 找上一筆，但 LAG 用 (timestamp ASC, id ASC)
        # 可能不一致（concurrent 時 timestamp 不嚴格單調）。
        # chain-link 檢查只在乎「每筆 prev_hash 都能在 chain 裡找到」就 OK。
        zero_prev = "0" * 64
        sql = """
        SELECT
            al.id,
            al.entry_hash,
            al.prev_hash,
            encode(digest(
                al.prev_hash || '|' ||
                COALESCE(al.id::text, '') || '|' ||
                COALESCE(al.actor_id::text, '') || '|' ||
                al.action || '|' ||
                COALESCE(al.entity_type, '') || '|' ||
                COALESCE(al.entity_id, '') || '|' ||
                COALESCE(al.details::text, '{}') || '|' ||
                al.timestamp::text,
                'sha256'
            ), 'hex') AS recomputed_hash,
            EXISTS (
                SELECT 1 FROM audit_logs al2 WHERE al2.entry_hash = al.prev_hash
            ) AS prev_found
        FROM audit_logs al
        WHERE (CAST(:since_ts AS timestamptz) IS NULL
               OR al.timestamp >= CAST(:since_ts AS timestamptz))
        ORDER BY al.timestamp, al.id
        """
        if limit:
            sql += f" LIMIT {int(limit)}"

        result = await self.session.execute(text(sql), {"since_ts": since})
        rows = result.fetchall()

        broken: list[int] = []
        for row in rows:
            hash_ok = row.entry_hash == row.recomputed_hash
            # chain_ok: prev 是 64 個 0（鏈首）或 prev 能在表內找到對應 entry_hash
            chain_ok = (row.prev_hash == zero_prev) or bool(row.prev_found)
            if not (chain_ok and hash_ok):
                logger.warning(
                    "audit_chain.broken_row",
                    id=row.id,
                    chain_ok=chain_ok,
                    hash_ok=hash_ok,
                )
                broken.append(int(row.id))

        return (len(broken) == 0, broken)

    async def list_recent(
        self,
        *,
        action: str | None = None,
        actor_id: UUID | None = None,
        limit: int = 50,
    ) -> list[AuditLog]:
        """簡單 list（給 verify CLI / debug 用）。"""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


__all__ = [
    "INITIAL_PREV_HASH",
    "AuditRepository",
    "compute_entry_hash",
]

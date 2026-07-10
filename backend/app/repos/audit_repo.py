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


# Phase 12 audit fix: compute_entry_hash + _serialize_details + _coerce_str 為死碼，且
# Python json.dumps separator 與 PG details::text 不一致；verify_chain 一律走 PG 端
# digest()（見下方 SQL），這些 helper 全部刪除避免誤用。


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
        # 1. hash_ok：每一筆重算 entry_hash 應與 DB 存的相同（timestamp 亦在雜湊 payload 內，
        #    故任何 timestamp 竄改/對調都會使 hash_ok=False 被抓到）。
        # 2. chain_ok：prev_hash 為 64 個 0（鏈首）或能在全表任一列找到對應 entry_hash（prev_found）。
        #    **刻意用「順序無關」的 EXISTS 而非 LAG**：trigger 的 NEW.timestamp=NOW() 是「交易開始
        #    時間」，可能與 advisory-lock 決定的實際鏈結順序相反；用 LAG(ORDER BY timestamp,id) 會在
        #    並發稽核寫入下把自洽的鏈誤報成斷裂（每日誤報 CRITICAL）。EXISTS 對「中段刪除」仍能抓到
        #    （被刪列的後繼者其 prev_hash 找不到對應），對「竄改」由 hash_ok 抓到；「尾端截斷」則由
        #    detect_tail_truncation() + checkpoint 錨定偵測。
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

    async def get_chain_tip(self) -> tuple[int, int | None, str | None]:
        """回傳目前鏈尾狀態 (row_count, last_id, last_entry_hash)。空表回 (0, None, None)。"""
        # 純量子查詢：即使空表也一定回一列（COUNT=0、其餘 NULL）
        sql = """
        SELECT
            (SELECT COUNT(*) FROM audit_logs) AS row_count,
            (SELECT id FROM audit_logs ORDER BY timestamp DESC, id DESC LIMIT 1) AS last_id,
            (SELECT entry_hash FROM audit_logs
              ORDER BY timestamp DESC, id DESC LIMIT 1) AS last_entry_hash
        """
        row = (await self.session.execute(text(sql))).first()
        if row is None:
            return (0, None, None)
        return (
            int(row.row_count or 0),
            int(row.last_id) if row.last_id is not None else None,
            row.last_entry_hash,
        )

    async def get_latest_checkpoint(self) -> tuple[int, int | None, str | None] | None:
        """取最近一次 checkpoint (row_count, last_id, last_entry_hash)；無則 None。"""
        sql = (
            "SELECT row_count, last_id, last_entry_hash "
            "FROM audit_checkpoints ORDER BY id DESC LIMIT 1"
        )
        row = (await self.session.execute(text(sql))).first()
        if row is None:
            return None
        return (
            int(row.row_count or 0),
            int(row.last_id) if row.last_id is not None else None,
            row.last_entry_hash,
        )

    async def detect_tail_truncation(self) -> tuple[bool, str | None]:
        """以最近 checkpoint 錨定，偵測「鏈尾最新數筆被刪除/竄改」。

        鏈結驗證抓不到尾端截斷（刪最後幾筆後殘存鏈仍自洽），故用外部 checkpoint 比對：
        - 目前列數 < checkpoint 列數 → 列數回退＝尾端被刪。
        - checkpoint 錨定的 last_entry_hash 已不存在於表 → 錨定列被刪/改。
        回 (ok, reason)。無 checkpoint（首次）視為 ok。
        """
        cp = await self.get_latest_checkpoint()
        if cp is None:
            return (True, None)
        cp_count, _cp_last_id, cp_last_hash = cp
        cur_count, _cur_last_id, _cur_last_hash = await self.get_chain_tip()
        if cur_count < cp_count:
            return (False, f"row_count regressed: {cur_count} < checkpoint {cp_count}")
        if cp_last_hash:
            exists = (
                await self.session.execute(
                    text("SELECT EXISTS(SELECT 1 FROM audit_logs WHERE entry_hash = :h) AS e"),
                    {"h": cp_last_hash},
                )
            ).scalar()
            if not exists:
                return (False, "checkpointed tip entry_hash missing (tail deleted/modified)")
        return (True, None)

    async def record_checkpoint(self) -> tuple[int, int | None, str | None]:
        """把目前鏈尾寫入 audit_checkpoints（append-only）。回寫入的 (row_count, last_id, last_hash)。

        僅應在 verify_chain + detect_tail_truncation 均通過後呼叫，避免把已損壞的鏈固化成基準。
        需 rw session（ta_service_rw 對 audit_checkpoints 有 INSERT，UPDATE/DELETE 已於 0019 撤銷）。
        """
        row_count, last_id, last_hash = await self.get_chain_tip()
        await self.session.execute(
            text(
                "INSERT INTO audit_checkpoints (row_count, last_id, last_entry_hash) "
                "VALUES (:c, :i, :h)"
            ),
            {"c": row_count, "i": last_id, "h": last_hash},
        )
        await self.session.commit()
        return (row_count, last_id, last_hash)

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
]

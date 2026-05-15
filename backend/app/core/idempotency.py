"""Phase 11 — Idempotency-Key 機制。

依 PLAN.md 第 14.5 章：
- POST 建立類接受 `Idempotency-Key` header（Redis db6, TTL 24h）
- 同 user + 同 key + 同 request hash → 回上次的 response（不重做）
- 同 user + 同 key 但 request 不同 → 422 IdempotencyConflictError
- 不同 user 用同 key → 視為不同（key 是 per-user namespace）

雙寫策略：
- 主要：Redis db=6（TTL 24h），快、不擋 request
- 備份：DB idempotency_keys 表（Redis 重啟時保命；寫失敗只 log 不 raise）

設計：
- check_existing(key, user_id, request_hash) → ResponseEntry | None
- record_response(key, user_id, request_hash, status_code, response) → None
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.errors import IdempotencyConflictError
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.models.idempotency import IDEMPOTENCY_TTL_HOURS, IdempotencyKey

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


# 24 小時（Redis TTL 用秒）
IDEMPOTENCY_TTL_SECONDS = IDEMPOTENCY_TTL_HOURS * 3600


def compute_request_hash(method: str, path: str, body: bytes | str | dict | None) -> str:
    """計算 request 指紋：SHA-256(method + path + body)。

    body 是 dict 時先 json.dumps（sort_keys=True 保穩定）；
    bytes / str / None 直接吃。
    """
    if body is None:
        body_bytes = b""
    elif isinstance(body, bytes):
        body_bytes = body
    elif isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")

    h = hashlib.sha256()
    h.update(method.upper().encode("ascii"))
    h.update(b"|")
    h.update(path.encode("utf-8"))
    h.update(b"|")
    h.update(body_bytes)
    return h.hexdigest()


@dataclass(frozen=True)
class IdempotencyEntry:
    """已記錄的 idempotency 回應。"""

    request_hash: str
    status_code: int
    response: Any


def _redis_key(user_id: UUID | str | None, key: str) -> str:
    """Redis key namespace：idem:{user_id|anon}:{key}。

    Per-user 命名空間（不同 user 用同 key 不會撞）。
    """
    uid = str(user_id) if user_id is not None else "anon"
    return f"idem:{uid}:{key}"


class IdempotencyService:
    """Idempotency 雙寫服務（Redis 為主、DB 為備）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check_existing(
        self,
        *,
        key: str,
        user_id: UUID | str | None,
        request_hash: str,
    ) -> IdempotencyEntry | None:
        """檢查 key 是否已有記錄。

        Returns:
            None — 沒見過，caller 可繼續處理 request
            IdempotencyEntry — 已存在且 hash 相同，直接回它的 response
        Raises:
            IdempotencyConflictError — key 存在但 request_hash 不同（攻擊或 client bug）
        """
        # 1. 先看 Redis
        rkey = _redis_key(user_id, key)
        redis = await get_redis(RedisDB.IDEMPOTENCY)
        try:
            cached = await redis.get(rkey)
        except Exception as e:  # pragma: no cover - redis 故障
            logger.warning("idempotency.redis_get_failed", error=str(e), key=key)
            cached = None

        if cached:
            try:
                data = json.loads(cached)
                if data.get("request_hash") != request_hash:
                    logger.warning(
                        "idempotency.hash_mismatch",
                        key=key,
                        user_id=str(user_id),
                    )
                    raise IdempotencyConflictError(
                        message_zh="同一個 Idempotency-Key 對應的請求內容不一致",
                        idempotency_key=key,
                    )
                return IdempotencyEntry(
                    request_hash=data["request_hash"],
                    status_code=int(data.get("status_code", 200)),
                    response=data.get("response"),
                )
            except IdempotencyConflictError:
                raise
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("idempotency.redis_decode_failed", error=str(e))
                # 退路：刪掉壞的 key
                await redis.delete(rkey)

        # 2. Redis miss 或壞掉 → 看 DB
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == key)
        if user_id is not None:
            uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
            stmt = stmt.where(IdempotencyKey.user_id == uid)

        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        # DB 命中但 hash 不符
        if row.request_hash != request_hash:
            logger.warning(
                "idempotency.db_hash_mismatch",
                key=key,
                user_id=str(user_id),
            )
            raise IdempotencyConflictError(
                message_zh="同一個 Idempotency-Key 對應的請求內容不一致",
                idempotency_key=key,
            )

        # DB 命中 → 回填 Redis（best-effort）
        entry = IdempotencyEntry(
            request_hash=row.request_hash,
            status_code=row.status_code or 200,
            response=row.response,
        )
        try:
            await redis.setex(
                rkey,
                IDEMPOTENCY_TTL_SECONDS,
                json.dumps(
                    {
                        "request_hash": entry.request_hash,
                        "status_code": entry.status_code,
                        "response": entry.response,
                    },
                    ensure_ascii=False,
                ),
            )
        except Exception as e:  # pragma: no cover
            logger.warning("idempotency.redis_repopulate_failed", error=str(e))

        return entry

    async def record_response(
        self,
        *,
        key: str,
        user_id: UUID | str | None,
        request_hash: str,
        status_code: int,
        response: Any,
    ) -> None:
        """寫入 Redis + DB（DB 寫失敗只 log 不 raise）。

        caller 在 commit 前/後都可呼叫（DB 寫入用 ON CONFLICT DO NOTHING 防重複）。
        """
        rkey = _redis_key(user_id, key)
        payload = {
            "request_hash": request_hash,
            "status_code": status_code,
            "response": response,
        }
        redis = await get_redis(RedisDB.IDEMPOTENCY)
        try:
            await redis.setex(
                rkey,
                IDEMPOTENCY_TTL_SECONDS,
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as e:  # pragma: no cover
            logger.warning("idempotency.redis_set_failed", error=str(e), key=key)

        # DB 持久備份（best-effort：失敗不擋 caller）
        import contextlib

        try:
            uid = None
            if user_id is not None:
                uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id

            expires_at = datetime.now(UTC) + timedelta(hours=IDEMPOTENCY_TTL_HOURS)
            stmt = (
                pg_insert(IdempotencyKey)
                .values(
                    key=key,
                    user_id=uid,
                    request_hash=request_hash,
                    response=response,
                    status_code=status_code,
                    expires_at=expires_at,
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
            await self.session.execute(stmt)
            await self.session.commit()
        except Exception as e:
            logger.warning("idempotency.db_write_failed", error=str(e), key=key)
            with contextlib.suppress(Exception):
                await self.session.rollback()


__all__ = [
    "IDEMPOTENCY_TTL_SECONDS",
    "IdempotencyEntry",
    "IdempotencyService",
    "compute_request_hash",
]

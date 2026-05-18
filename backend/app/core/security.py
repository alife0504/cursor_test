"""Phase 8 — 密碼 hash / JWT 簽發解碼 / Token 黑名單。

依 PLAN.md 第 19.1 章認證授權 + 第 19.4 章 Secret 管理（雙 key rotation）。

設計重點：
- bcrypt cost=12（登入慢 ~200ms 是正常的；不要降）
- HS256 + 32-byte 以上 SECRET_KEY（config 已驗）
- JWTService 用 dual-key：sign 永遠用 current；decode 先試 current，失敗再試 previous
- Token blacklist 用 Redis db3，TTL = token 剩餘 exp 秒數（避免永久占記憶體）
- 全部時間用 datetime.now(timezone.utc)，禁用 datetime.utcnow()（Python 3.12 deprecate）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import bcrypt
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.errors import AuthError
from app.core.logging_config import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.core.config import Settings

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────
# 密碼 hash
# ─────────────────────────────────────────────────────────

_BCRYPT_ROUNDS = 12
"""bcrypt cost 因子（≈ 200ms / verify）。"""

# Dummy hash 用來抵抗 timing attack：當使用者不存在時，仍 verify 一次以等候相同時間。
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"timing-attack-dummy-password", bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
).decode("utf-8")


def hash_password(password: str) -> str:
    """以 bcrypt cost=12 hash 密碼。回傳 utf-8 字串（直接存 DB）。"""
    if not isinstance(password, str) or not password:
        raise ValueError("password 不可為空")
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """比對明文與 bcrypt hash。任何異常一律回 False。"""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def constant_time_dummy_verify() -> None:
    """使用者不存在時呼叫一次 bcrypt 抵抗 timing attack。

    為什麼：若 user 不存在直接 return，會比「user 存在但密碼錯」快得多，
    攻擊者可由耗時差異列舉 email。這個 dummy verify 故意耗用相當時間。
    """
    bcrypt.checkpw(b"timing-attack-dummy-password", _DUMMY_PASSWORD_HASH.encode("utf-8"))


# ─────────────────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────────────────


class JWTService:
    """JWT 簽發 / 解碼 — dual-key rotation 過渡期支援。

    Sign：永遠用 current_key。
    Decode：先試 current_key，InvalidSignatureError 才退試 previous_key（並 warning log）。
    """

    ALGORITHM = "HS256"
    ACCESS_TTL = timedelta(minutes=15)
    REFRESH_TTL = timedelta(days=7)

    def __init__(self, settings: Settings) -> None:
        self.current_key: str = settings.SECRET_KEY
        self.previous_key: str | None = settings.SECRET_KEY_PREVIOUS

    # ── access ──────────────────────────────────────
    def create_access_token(
        self,
        user_id: UUID,
        role: str,
        *,
        ttl: timedelta | None = None,
    ) -> tuple[str, str]:
        """簽 access token，回 (token, jti)。"""
        now = datetime.now(UTC)
        jti = str(uuid4())
        exp = now + (ttl or self.ACCESS_TTL)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "role": role,
            "type": "access",
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, self.current_key, algorithm=self.ALGORITHM)
        return token, jti

    # ── refresh ─────────────────────────────────────
    def create_refresh_token(
        self,
        user_id: UUID,
        *,
        ttl: timedelta | None = None,
    ) -> tuple[str, str, datetime]:
        """簽 refresh token，回 (token, jti, expires_at)。"""
        now = datetime.now(UTC)
        jti = str(uuid4())
        exp = now + (ttl or self.REFRESH_TTL)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": "refresh",
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, self.current_key, algorithm=self.ALGORITHM)
        return token, jti, exp

    # ── decode ──────────────────────────────────────
    def decode(self, token: str) -> dict[str, Any]:
        """解碼 + 驗章。失敗一律 raise AuthError。"""
        if not token:
            raise AuthError(message_zh="Token 不可為空")

        # 先試 current key
        try:
            return jwt.decode(
                token,
                self.current_key,
                algorithms=[self.ALGORITHM],
            )
        except ExpiredSignatureError as e:
            # 過期：無論哪個 key 簽的都不接受
            raise AuthError(message_zh="Token 已過期") from e
        except JWTError as primary_err:
            # current key 驗失敗 → 試 previous key（rotation 過渡期）
            if self.previous_key:
                try:
                    payload = jwt.decode(
                        token,
                        self.previous_key,
                        algorithms=[self.ALGORITHM],
                    )
                    logger.warning(
                        "jwt.decoded_with_previous_key",
                        jti=payload.get("jti"),
                        sub=payload.get("sub"),
                    )
                    return payload
                except ExpiredSignatureError as e:
                    raise AuthError(message_zh="Token 已過期") from e
                except JWTError as e:
                    raise AuthError(message_zh="Token 簽名無效") from e
            raise AuthError(message_zh="Token 簽名無效") from primary_err


# ─────────────────────────────────────────────────────────
# Token blacklist
# ─────────────────────────────────────────────────────────


class TokenBlacklist:
    """Redis db3 上的 JWT jti 黑名單。

    Key: bl:jti:{jti}  Value: "1"  TTL: token 剩餘 exp 秒數。
    TTL 用「剩餘秒」而非「固定 7 天」是為了避免永久占記憶體。
    """

    KEY_PREFIX = "bl:jti:"

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _key(jti: str) -> str:
        return f"{TokenBlacklist.KEY_PREFIX}{jti}"

    async def add(self, jti: str, ttl_seconds: int) -> None:
        """加入黑名單；ttl_seconds ≤ 0 直接略過（已過期不必加）。"""
        if not jti or ttl_seconds <= 0:
            return
        await self.redis.setex(self._key(jti), int(ttl_seconds), "1")

    async def is_blacklisted(self, jti: str) -> bool:
        if not jti:
            return False
        return bool(await self.redis.exists(self._key(jti)))


def ttl_seconds_from_exp(exp: int) -> int:
    """從 JWT exp（epoch second）計算剩餘秒數；不可為負。"""
    now = int(datetime.now(UTC).timestamp())
    return max(0, exp - now)


__all__ = [
    "JWTService",
    "TokenBlacklist",
    "constant_time_dummy_verify",
    "hash_password",
    "ttl_seconds_from_exp",
    "verify_password",
]

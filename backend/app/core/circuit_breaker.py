"""Circuit Breaker — 防止連續失敗的下游服務拖垮上游。

依 PLAN.md 第 14.3 章設計：
- CLOSED → OPEN：連續 N 次失敗（預設 5）
- OPEN → HALF_OPEN：等 timeout（預設 600s）
- HALF_OPEN → CLOSED：1 次成功
- HALF_OPEN → OPEN：1 次失敗

使用方式：
    cb = get_or_create_breaker("finmind")
    if cb.state == CircuitState.OPEN:
        raise ExternalServiceError(...)
    try:
        result = await some_call()
        cb.record_success()
    except Exception:
        cb.record_failure()
        raise
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """單一 circuit breaker 實例。

    一個 source（如 "finmind"、"yfinance"、"gemini"）配一個 instance。
    state 變化時 log critical（P11+ 改 event bus 通知 admin）。
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold or settings.CB_FAILURE_THRESHOLD
        self.timeout_seconds = timeout_seconds or settings.CB_OPEN_TIMEOUT_S

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """目前狀態（自動處理 OPEN → HALF_OPEN 過渡）。"""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.timeout_seconds:
                # 不在這裡修改（避免 race），透過下次 record_*() 推進
                return CircuitState.HALF_OPEN
        return self._state

    def is_open(self) -> bool:
        """便利方法：判斷是否在「拒絕呼叫」狀態。"""
        return self.state == CircuitState.OPEN

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def record_success(self) -> None:
        """成功 → reset / 從 HALF_OPEN 回 CLOSED。"""
        async with self._lock:
            current = self.state
            if current == CircuitState.HALF_OPEN:
                logger.info("circuit_breaker.recovered", name=self.name)
                self._state = CircuitState.CLOSED
                self._opened_at = None
                self._failure_count = 0
            elif current == CircuitState.CLOSED:
                # 連續成功，reset failure count
                self._failure_count = 0

    async def record_failure(self) -> None:
        """失敗 → 累計 / 觸發 OPEN / HALF_OPEN 失敗回 OPEN。"""
        async with self._lock:
            current = self.state

            if current == CircuitState.HALF_OPEN:
                # half-open 試一次失敗 → 立即重新 OPEN
                logger.critical(
                    "circuit_breaker.reopened",
                    name=self.name,
                    failure_count=self._failure_count,
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                return

            if current == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    logger.critical(
                        "circuit_breaker.opened",
                        name=self.name,
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                    )
                    self._state = CircuitState.OPEN
                    self._opened_at = time.monotonic()

    async def reset(self) -> None:
        """手動 reset（運維 / 測試用）。"""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            logger.info("circuit_breaker.manually_reset", name=self.name)

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name} state={self.state} failures={self._failure_count}>"
        )


# ── Registry ──────────────────────────────────────────
# 全域 dict（by name），P5+ 會 lazy 註冊每個 data source / LLM provider 的 breaker

CIRCUIT_BREAKERS: dict[str, CircuitBreaker] = {}


def get_or_create_breaker(
    name: str,
    *,
    failure_threshold: int | None = None,
    timeout_seconds: int | None = None,
) -> CircuitBreaker:
    """取得 / 註冊 circuit breaker。"""
    if name not in CIRCUIT_BREAKERS:
        CIRCUIT_BREAKERS[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
        )
    return CIRCUIT_BREAKERS[name]


__all__ = [
    "CIRCUIT_BREAKERS",
    "CircuitBreaker",
    "CircuitState",
    "get_or_create_breaker",
]

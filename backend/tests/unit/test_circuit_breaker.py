"""Circuit Breaker 單元測試（依 PLAN 第 P3 章節 W）。"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitState, get_or_create_breaker

pytestmark = pytest.mark.unit


@pytest.fixture
def cb() -> CircuitBreaker:
    """每個 test 一個獨立 breaker（threshold=3 縮短測試時間）。"""
    return CircuitBreaker(name="test-source", failure_threshold=3, timeout_seconds=1)


def test_initially_closed(cb: CircuitBreaker) -> None:
    """新建 breaker 應在 CLOSED state。"""
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert not cb.is_open()


@pytest.mark.asyncio
async def test_opens_after_threshold_failures(cb: CircuitBreaker) -> None:
    """連續 N 次失敗 → OPEN。"""
    for _ in range(3):
        await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.is_open()
    assert cb.failure_count == 3


@pytest.mark.asyncio
async def test_failures_below_threshold_stay_closed(cb: CircuitBreaker) -> None:
    """N-1 次失敗 → 仍 CLOSED。"""
    for _ in range(2):
        await cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 2


@pytest.mark.asyncio
async def test_half_open_after_timeout(cb: CircuitBreaker) -> None:
    """OPEN 後等 timeout → state property 回 HALF_OPEN。"""
    for _ in range(3):
        await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    # 等 timeout（fixture timeout=1s）
    await asyncio.sleep(1.1)
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_returns_to_closed_on_success_in_half_open(cb: CircuitBreaker) -> None:
    """HALF_OPEN 跑一次成功 → CLOSED。"""
    for _ in range(3):
        await cb.record_failure()
    await asyncio.sleep(1.1)
    assert cb.state == CircuitState.HALF_OPEN
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_returns_to_open_on_failure_in_half_open(cb: CircuitBreaker) -> None:
    """HALF_OPEN 跑一次失敗 → 立即重新 OPEN。"""
    for _ in range(3):
        await cb.record_failure()
    await asyncio.sleep(1.1)
    assert cb.state == CircuitState.HALF_OPEN
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_success_in_closed_resets_failure_count(cb: CircuitBreaker) -> None:
    """CLOSED 中一次成功 → reset failure count（避免歷史失敗累積觸發 OPEN）。"""
    await cb.record_failure()
    await cb.record_failure()
    assert cb.failure_count == 2
    await cb.record_success()
    assert cb.failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_manual_reset(cb: CircuitBreaker) -> None:
    """reset() 應強制回 CLOSED 並清計數。"""
    for _ in range(3):
        await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    await cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_get_or_create_breaker_singleton() -> None:
    """同名 source 應回同一個 breaker instance。"""
    cb1 = get_or_create_breaker("singleton-test-1")
    cb2 = get_or_create_breaker("singleton-test-1")
    assert cb1 is cb2

    # 不同名應為不同 instance
    cb3 = get_or_create_breaker("singleton-test-2")
    assert cb3 is not cb1


# 抑制 unused import warning
_ = time

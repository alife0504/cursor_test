"""_probe_with_retry — 啟動探測退避重試。

暫時失敗會重試、依賴恢復就成功啟動；持續失敗用盡 retries 才 raise（fail-fast）。
這是「網站隨時停止服務」修補的一環：避免冷啟排序 / 休眠喚醒 / redis 重啟時，
一啟動就 raise 殺掉整個 process。
"""

from __future__ import annotations

import asyncio

import pytest

from app.main import _probe_with_retry

pytestmark = pytest.mark.unit


def test_first_try_success() -> None:
    calls = {"n": 0}

    async def probe() -> None:
        calls["n"] += 1

    asyncio.run(_probe_with_retry(probe, name="x", retries=5, delay_s=0.0))
    assert calls["n"] == 1


def test_succeeds_after_transient_failures() -> None:
    calls = {"n": 0}

    async def probe() -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("not ready yet")

    asyncio.run(_probe_with_retry(probe, name="x", retries=5, delay_s=0.0))
    assert calls["n"] == 3  # 第 3 次才成功


def test_raises_after_exhausting_retries() -> None:
    async def probe() -> None:
        raise RuntimeError("always down")

    with pytest.raises(RuntimeError, match="always down"):
        asyncio.run(_probe_with_retry(probe, name="x", retries=3, delay_s=0.0))

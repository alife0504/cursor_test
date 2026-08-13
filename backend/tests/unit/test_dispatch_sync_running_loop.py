"""回歸測試：dispatch_sync 在「已有 running event loop」時仍須真的執行 dispatch。

背景（第三輪審計 S02）：run_analysis 的 _async_pipeline 在 worker 的 running loop 內呼叫
dispatch_sync，舊實作用 asyncio.run() 會丟 RuntimeError 被 except 吞成 []，導致「分析完成」
通知永遠沒送出。整合測試因直接 await dispatch()「假綠」而未抓到。此測試在 running loop 內
呼叫 dispatch_sync 並驗證 dispatch 真的執行（_resolve_targets 被呼叫）。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.notifications import NotificationDispatcher, NotifyEvent, NotifyLevel


async def test_dispatch_sync_executes_inside_running_loop() -> None:
    d = NotificationDispatcher()
    # 攔截 _resolve_targets（sync）回空清單，避免碰 DB / 真 notifier
    resolve = MagicMock(return_value=[])
    d._resolve_targets = resolve  # type: ignore[method-assign]

    event = NotifyEvent(event_type="test", title="t", body="b", level=NotifyLevel.INFO)

    # 本測試本身在 pytest 的 running event loop 內
    result = d.dispatch_sync(event)

    assert resolve.called, (
        "dispatch_sync 在 running loop 內未執行 dispatch —— 被 asyncio.run 的 "
        "RuntimeError 吞掉，通知會永遠沒送出（S02 回歸）"
    )
    assert result == []

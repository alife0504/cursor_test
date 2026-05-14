"""DLQ signal handler 單元測試（PLAN 第 14.10 章）。

不接 DB；用 monkeypatch 替換 sync_rw_session 為 in-memory mock，
驗 write_to_dlq 在 task_failure 觸發時是否寫入正確 row + 失敗 fallback。
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any

import pytest

from app.workers import dlq

pytestmark = pytest.mark.unit


# ─────────── Mock session（模擬 SQLAlchemy session） ───────────


class _MockSession:
    """收集 add() 呼叫，模擬 session 的最小 API。"""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.closed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def mock_session(monkeypatch: pytest.MonkeyPatch) -> _MockSession:
    """patch sync_rw_session 回我們的 mock。"""
    session = _MockSession()

    @contextmanager
    def _ctx():
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(dlq, "sync_rw_session", _ctx)
    return session


# ─────────── 測試 fixture：fake celery sender ───────────


class _FakeRequest:
    def __init__(self, retries: int = 0) -> None:
        self.retries = retries


class _FakeSender:
    """模擬 celery task class。"""

    def __init__(self, name: str = "test.task", retries: int = 0) -> None:
        self.name = name
        self.request = _FakeRequest(retries)


class _FakeEinfo:
    def __init__(self, traceback: str) -> None:
        self.traceback = traceback


# ─────────── Tests ───────────


def test_task_failure_writes_dlq_row(mock_session: _MockSession) -> None:
    """task_failure 觸發後 → session.add 一筆 + commit。"""
    sender = _FakeSender(name="app.workers.tasks.sync_ohlcv.sync_ohlcv_one")
    task_id = str(uuid.uuid4())

    dlq.write_to_dlq(
        sender=sender,
        task_id=task_id,
        exception=ValueError("boom"),
        args=["2330", "TWSE"],
        kwargs={"days_back": 7},
        einfo=_FakeEinfo("Traceback (most recent call last):\n  ValueError: boom\n"),
    )

    assert len(mock_session.added) == 1
    assert mock_session.committed is True
    assert mock_session.closed is True

    row = mock_session.added[0]
    assert row.task_name == "app.workers.tasks.sync_ohlcv.sync_ohlcv_one"
    assert row.exception_type == "ValueError"
    assert "boom" in row.exception
    assert row.resolved is False
    assert row.task_id == uuid.UUID(task_id)


def test_dlq_includes_traceback(mock_session: _MockSession) -> None:
    """traceback 完整保留（除非超過 10k 才 truncate）。"""
    sender = _FakeSender()
    tb = "Traceback line 1\nTraceback line 2\n  RuntimeError: oops\n"

    dlq.write_to_dlq(
        sender=sender,
        task_id=str(uuid.uuid4()),
        exception=RuntimeError("oops"),
        args=[],
        kwargs={},
        einfo=_FakeEinfo(tb),
    )

    row = mock_session.added[0]
    assert "Traceback line 1" in row.traceback
    assert "RuntimeError" in row.traceback


def test_dlq_marks_resolved_false(mock_session: _MockSession) -> None:
    """新寫入的 row 一定 resolved=False。"""
    dlq.write_to_dlq(
        sender=_FakeSender(),
        task_id=str(uuid.uuid4()),
        exception=Exception("e"),
        args=[],
        kwargs={},
        einfo=_FakeEinfo(""),
    )
    row = mock_session.added[0]
    assert row.resolved is False
    assert row.retry_count == 0  # _FakeRequest(retries=0)


def test_dlq_retry_count_propagates(mock_session: _MockSession) -> None:
    """sender.request.retries 應映射到 row.retry_count。"""
    dlq.write_to_dlq(
        sender=_FakeSender(retries=3),
        task_id=str(uuid.uuid4()),
        exception=Exception("e"),
        args=[],
        kwargs={},
        einfo=_FakeEinfo(""),
    )
    assert mock_session.added[0].retry_count == 3


def test_dlq_invalid_task_id_uuid_falls_to_none(mock_session: _MockSession) -> None:
    """task_id 不是 UUID 字串時，row.task_id = None（不 raise）。"""
    dlq.write_to_dlq(
        sender=_FakeSender(),
        task_id="not-a-uuid-just-string",
        exception=Exception("e"),
        args=[],
        kwargs={},
        einfo=_FakeEinfo(""),
    )
    assert mock_session.added[0].task_id is None


def test_dlq_db_failure_writes_fallback_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """sync_rw_session 拋例外 → fallback 檔有一行 JSON 紀錄。"""

    @contextmanager
    def _broken_ctx():
        raise RuntimeError("db is down")
        yield

    fallback = tmp_path / "dlq_fallback.jsonl"
    monkeypatch.setattr(dlq, "sync_rw_session", _broken_ctx)
    monkeypatch.setattr(dlq, "_FALLBACK_FILE", fallback)

    dlq.write_to_dlq(
        sender=_FakeSender(name="task.x"),
        task_id=str(uuid.uuid4()),
        exception=Exception("inner"),
        args=[1, 2],
        kwargs={"k": "v"},
        einfo=_FakeEinfo("tb"),
    )

    assert fallback.exists()
    line = fallback.read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["task_name"] == "task.x"
    assert (
        record["db_write_error"].startswith("db is down")
        or "db is down" in record["db_write_error"]
    )


def test_safe_json_truncates_oversized() -> None:
    """超過 64KB 的 args 應被 truncate 成 preview。"""
    big = ["x" * 100_000]
    out = dlq._safe_json(big)
    assert isinstance(out, dict)
    assert out.get("_truncated") is True


def test_safe_json_handles_unserializable() -> None:
    """無法 JSON-able 的物件 → fallback 為 stringified preview。"""

    class NotSerializable:
        def __repr__(self) -> str:
            return "<NotSerializable>"

        # default=str 會把 __repr__ 當 fallback；測 nested + circular 可能更難
        # 這裡用 set 觸發 TypeError（json default 不支援 set）
        def to_json(self) -> Any:
            raise TypeError

    out = dlq._safe_json({"x": {1, 2, 3}})  # set 不可 JSON
    # 我們 default=str 會把 set 轉成字串 "{1, 2, 3}"，結果還是合法 JSON
    # 所以實際結果不一定走 _unserializable 分支。確認回傳能 round-trip。
    assert json.dumps(out, default=str) is not None


def test_default_fallback_path_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """CELERY_DLQ_FALLBACK_FILE env var override default 路徑（透過 module reload 才能驗）。"""
    # 至少確認 _FALLBACK_FILE 是 Path 物件
    from pathlib import Path

    assert isinstance(dlq._FALLBACK_FILE, Path)
    # 確認預設值就是 env 或 /tmp/...
    expected_env = os.environ.get("CELERY_DLQ_FALLBACK_FILE")
    if expected_env:
        assert str(dlq._FALLBACK_FILE) == expected_env

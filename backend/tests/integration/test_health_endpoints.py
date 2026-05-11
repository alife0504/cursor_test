"""Health endpoints integration test（依 PLAN 第 P3 章節 V）。

需 docker compose up（三服務 healthy）才能跑完全部 case。
若 DB / Redis / Qdrant 不可達，會 graceful skip 對應 ready 測試。

測試項：
- /health/live 一律 200
- /health/ready 三服務 OK 時 200，任一掛時 503
- /health/seeded 暫回 false（P7 之後變 true）
- envelope 格式正確
- response 含 X-Request-ID header
"""

from __future__ import annotations

import os
import socket
from typing import Any

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.integration


# 測試環境跳過 startup probe（避免單元測試需 docker 起來）
os.environ["PYTEST_RUNNING"] = "true"


@pytest.fixture
def client() -> TestClient:
    """建立 TestClient（會跑 lifespan，PYTEST_RUNNING=true 跳過 probe）。"""
    from app.main import app

    with TestClient(app) as c:
        yield c


def _docker_services_reachable() -> bool:
    """簡單 socket 檢測 docker 服務是否可達（不可達就 skip ready 測試）。"""
    for host, port in [("localhost", 5432), ("localhost", 6379), ("localhost", 6333)]:
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


# ────────────────────── /health/live ──────────────────────


def test_health_live_returns_200(client: TestClient) -> None:
    """/health/live 必回 200（不依賴下游服務）。"""
    r = client.get("/health/live")
    assert r.status_code == 200


def test_health_live_envelope_format(client: TestClient) -> None:
    """envelope 格式：{data: {status, version}, meta: {trace_id, version, timestamp}}。"""
    r = client.get("/health/live")
    body = r.json()
    assert "data" in body
    assert body["data"]["status"] == "alive"
    assert "version" in body["data"]
    assert "meta" in body
    assert "trace_id" in body["meta"]
    assert "timestamp" in body["meta"]


def test_health_live_has_request_id_header(client: TestClient) -> None:
    """response 必含 X-Request-ID header。"""
    r = client.get("/health/live")
    assert "X-Request-ID" in r.headers


def test_health_live_has_security_headers(client: TestClient) -> None:
    """SecurityHeadersMiddleware 必加上以下 header。"""
    r = client.get("/health/live")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers


# ────────────────────── /health/seeded ──────────────────────


def test_health_seeded_returns_false_initially(client: TestClient) -> None:
    """P7 前 seeded 永遠 false。"""
    r = client.get("/health/seeded")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["seeded"] is False
    assert "P7" in body["data"]["reason"]


# ────────────────────── /health/ready ──────────────────────


def test_health_ready_returns_503_when_deps_down(client: TestClient) -> None:
    """三服務有任一掛時，ready 回 503。

    這個測試在 docker 沒跑時會跑（因為 deps 不可達）。
    docker 跑時會 skip。
    """
    if _docker_services_reachable():
        pytest.skip("Docker services up → 此 test 應在 services down 時跑")
    r = client.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["data"]["status"] == "not_ready"
    assert "dependencies" in body["data"]


def test_health_ready_returns_200_when_all_deps_ok(client: TestClient) -> None:
    """三服務都 OK 時 ready 回 200。

    docker 沒跑時 skip。
    """
    if not _docker_services_reachable():
        pytest.skip("Docker services not reachable; need `make up`")
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "ready"
    assert all(v == "ok" for v in body["data"]["dependencies"].values())


# ────────────────────── 404 / envelope error ──────────────────────


def test_404_returns_envelope_error(client: TestClient) -> None:
    """非存在路徑 → 404 + envelope 格式（不洩漏 stack trace）。"""
    r = client.get("/nonexistent-path-xyz")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] in ("NOT_FOUND", "HTTP_404")
    assert "trace_id" in body["error"]


def test_405_method_not_allowed(client: TestClient) -> None:
    """錯方法 → 405 + envelope。"""
    r = client.post("/health/live")  # POST 對 GET only 路徑
    assert r.status_code == 405
    body = r.json()
    assert "error" in body


# 抑制 unused import warning
_ = Any

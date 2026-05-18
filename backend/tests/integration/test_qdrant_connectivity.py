"""Qdrant 連線測試。

需 docker compose up（qdrant healthy）。

驗證：
1. /healthz 不需 API key（healthcheck 路徑）
2. /collections 需 API key（read API）
3. 不帶 api-key 應 401 / 403
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration


def _skip_if_no_qdrant(host: str, port: int) -> None:
    import socket

    try:
        with socket.create_connection((host, port), timeout=2):
            return
    except OSError:
        pytest.skip(f"Qdrant not reachable at {host}:{port} (start with `make up`)")


# ───────────────────────── 測試 ─────────────────────────


def test_qdrant_healthz_no_api_key(qdrant_host: str, qdrant_port: int) -> None:
    """/healthz 不需 API key（給 docker healthcheck 用）。"""
    _skip_if_no_qdrant(qdrant_host, qdrant_port)
    url = f"http://{qdrant_host}:{qdrant_port}/healthz"
    r = httpx.get(url, timeout=5)
    assert r.status_code == 200, f"/healthz 應 200，實際 {r.status_code}: {r.text}"


def test_qdrant_collections_requires_api_key(qdrant_host: str, qdrant_port: int) -> None:
    """/collections 不帶 api-key 應 401 / 403。"""
    _skip_if_no_qdrant(qdrant_host, qdrant_port)
    url = f"http://{qdrant_host}:{qdrant_port}/collections"
    r = httpx.get(url, timeout=5)
    assert r.status_code in (
        401,
        403,
    ), f"沒帶 api-key 應 401/403，實際 {r.status_code}: {r.text[:100]}"


def test_qdrant_collections_with_api_key(
    env_vars: dict[str, Any], qdrant_host: str, qdrant_port: int
) -> None:
    """帶正確 api-key 應可列 collections。"""
    _skip_if_no_qdrant(qdrant_host, qdrant_port)
    api_key = env_vars.get("QDRANT_API_KEY", "")
    assert api_key, "QDRANT_API_KEY 未設"

    url = f"http://{qdrant_host}:{qdrant_port}/collections"
    r = httpx.get(url, headers={"api-key": api_key}, timeout=5)
    assert r.status_code == 200, f"帶正確 api-key 應 200，實際 {r.status_code}: {r.text[:200]}"

    # 回應結構：{ "result": { "collections": [...] }, "status": "ok", ... }
    data = r.json()
    assert "result" in data
    assert "collections" in data["result"]
    assert isinstance(data["result"]["collections"], list)


def test_qdrant_wrong_api_key_rejected(qdrant_host: str, qdrant_port: int) -> None:
    """錯誤的 api-key 應 401 / 403。"""
    _skip_if_no_qdrant(qdrant_host, qdrant_port)
    url = f"http://{qdrant_host}:{qdrant_port}/collections"
    r = httpx.get(url, headers={"api-key": "wrong-key-xxx"}, timeout=5)
    assert r.status_code in (
        401,
        403,
    ), f"錯 api-key 應 401/403，實際 {r.status_code}: {r.text[:100]}"

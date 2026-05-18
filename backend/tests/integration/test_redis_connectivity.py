"""Redis 連線測試。

需 docker compose up（redis healthy）。

驗證：
1. 用 password 連線 → ping 通
2. SET / GET / DEL 正常
3. 沒設 password 連線 → 失敗（NOAUTH 或 connection error）
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _skip_if_no_redis(host: str, port: int) -> None:
    import socket

    try:
        with socket.create_connection((host, port), timeout=2):
            return
    except OSError:
        pytest.skip(f"Redis not reachable at {host}:{port} (start with `make up`)")


def _redis_client(host: str, port: int, password: str | None) -> Any:
    """回傳 redis.Redis instance（同步版，方便測試）。"""
    import redis

    return redis.Redis(
        host=host,
        port=port,
        password=password,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )


# ───────────────────────── 測試 ─────────────────────────


def test_redis_ping_with_password(
    env_vars: dict[str, Any], redis_host: str, redis_port: int
) -> None:
    """用正確 password 應可 ping。"""
    _skip_if_no_redis(redis_host, redis_port)
    pwd = env_vars.get("REDIS_PASSWORD", "")
    assert pwd, "REDIS_PASSWORD 未設"
    client = _redis_client(redis_host, redis_port, pwd)
    assert client.ping() is True


def test_redis_set_get_del(env_vars: dict[str, Any], redis_host: str, redis_port: int) -> None:
    """SET / GET / DEL 完整流程。"""
    _skip_if_no_redis(redis_host, redis_port)
    pwd = env_vars.get("REDIS_PASSWORD", "")
    client = _redis_client(redis_host, redis_port, pwd)

    key = "phase02:test:key"
    value = "hello-world-2330"

    # SET
    assert client.set(key, value, ex=10) is True

    # GET
    got = client.get(key)
    assert got == value

    # DEL
    deleted = client.delete(key)
    assert deleted == 1

    # GET 應為 None
    assert client.get(key) is None


def test_redis_no_password_fails(redis_host: str, redis_port: int) -> None:
    """不帶 password 連線應失敗（NOAUTH 或 AuthenticationError）。"""
    _skip_if_no_redis(redis_host, redis_port)
    import redis as redis_lib

    client = _redis_client(redis_host, redis_port, None)
    with pytest.raises((redis_lib.AuthenticationError, redis_lib.ResponseError)):
        client.ping()


def test_redis_wrong_password_fails(redis_host: str, redis_port: int) -> None:
    """錯密碼應 raise AuthenticationError。"""
    _skip_if_no_redis(redis_host, redis_port)
    import redis as redis_lib

    client = _redis_client(redis_host, redis_port, "wrong-password-xxx")
    with pytest.raises((redis_lib.AuthenticationError, redis_lib.ResponseError)):
        client.ping()

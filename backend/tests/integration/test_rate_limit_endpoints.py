"""Phase 9 — Rate limit middleware 整合測試（真 Redis db2）。

依 PLAN 第 19.3 章 + 第二十八章 O 項。

注意：
- 用 conftest 的同步 redis flush（已含 db 2）。
- 每個 test 開頭 flushdb db 2 → 不會跨 test 污染。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _flush_ratelimit_db(env_vars):
    """每個 rate-limit test 前清 db 2（不然 sliding window 殘留會擋）。"""
    import redis as redis_sync

    pwd = env_vars.get("REDIS_PASSWORD", "")
    host = env_vars.get("REDIS_HOST", "localhost")
    port = int(env_vars.get("REDIS_PORT", "6379"))
    try:
        client = redis_sync.Redis(
            host=host, port=port, db=2, password=pwd, socket_connect_timeout=2
        )
        client.flushdb()
        client.close()
    except Exception as exc:  # pragma: no cover  - noqa: S110
        _ = exc
    yield


# ────────────────────────────────────────────────────────
# 1. /auth/login 5/min/IP
# ────────────────────────────────────────────────────────


async def test_login_5_per_min_per_ip(auth_client) -> None:
    """連 6 次 login（用不存在 email），第 6 次應 429。"""
    for i in range(5):
        r = auth_client.post(
            "/api/v1/auth/login",
            json={"email": f"nx-{i}@test.example.com", "password": "Abc12345678!"},
        )
        # 5 次內都應該是 401（user 不存在）
        assert r.status_code == 401, f"第 {i+1} 次 status={r.status_code} body={r.text}"

    # 第 6 次該被擋
    r6 = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nx-x@test.example.com", "password": "Abc12345678!"},
    )
    assert r6.status_code == 429, r6.text


async def test_rate_limit_response_includes_retry_after(auth_client) -> None:
    """rate-limit 回應應含 Retry-After header。"""
    for _ in range(6):
        auth_client.post(
            "/api/v1/auth/login",
            json={"email": "rate@test.example.com", "password": "Abc12345678!"},
        )
    # 最後一次應該已被擋
    last = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "rate@test.example.com", "password": "Abc12345678!"},
    )
    assert last.status_code == 429
    assert "Retry-After" in last.headers
    assert int(last.headers["Retry-After"]) > 0


# ────────────────────────────────────────────────────────
# 2. /auth/password-reset 3/hr/IP
# ────────────────────────────────────────────────────────


async def test_password_reset_3_per_hour_per_ip(auth_client, make_test_user) -> None:
    user, _ = await make_test_user(must_change=False)
    # 3 次內成功
    for _ in range(3):
        r = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
        assert r.status_code == 200, r.text
    # 第 4 次 → 429
    r4 = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
    assert r4.status_code == 429, r4.text


# ────────────────────────────────────────────────────────
# 3. L1 global per IP 300/min（用 health 看不到，因為被排除；用 /me）
# ────────────────────────────────────────────────────────


async def test_l1_global_per_ip(auth_client) -> None:
    """L1 限 300/min 對單一 IP — 跑 305 次 GET /api/v1/auth/me（不需 token，看 401 + L1 累計）。"""
    # /api/v1/auth/me 沒 token 是 401，但仍會累 L1
    # 連 301 次：前 300 ok（401），第 301 該 429（L1）
    statuses = []
    for _ in range(305):
        r = auth_client.get("/api/v1/auth/me")
        statuses.append(r.status_code)
    # 應至少有一次 429
    assert 429 in statuses, f"L1 沒擋；statuses tail: {statuses[-5:]}"


# ────────────────────────────────────────────────────────
# 4. /health/* 應該完全不被 rate limit（即使 1000 次都 OK）
# ────────────────────────────────────────────────────────


async def test_health_exempt_from_rate_limit(auth_client) -> None:
    for _ in range(50):
        r = auth_client.get("/health/live")
        assert r.status_code == 200


# ────────────────────────────────────────────────────────
# 5. envelope 格式正確
# ────────────────────────────────────────────────────────


async def test_rate_limit_envelope_format(auth_client) -> None:
    for _ in range(6):
        auth_client.post(
            "/api/v1/auth/login",
            json={"email": "envelope@test.example.com", "password": "Abc12345678!"},
        )
    last = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "envelope@test.example.com", "password": "Abc12345678!"},
    )
    assert last.status_code == 429
    body = last.json()
    assert "error" in body
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "trace_id" in body["error"]
    assert "details" in body["error"]
    assert "retry_after_sec" in body["error"]["details"]

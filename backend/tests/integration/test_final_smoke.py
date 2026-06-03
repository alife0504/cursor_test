"""Phase 20 — v1.0 最終 smoke test。

PLAN 第二十七章 ▌Phase 20 第 K 節（≥ 5 個 final smoke）：

  1. test_can_login_as_admin                       — 用 admin 帳號登入流程通
  2. test_dashboard_endpoint_returns_data          — /dashboard 系列 endpoint 通
  3. test_full_analysis_completes_within_smoke_envelope — 走完整 workflow（seed-mock）
  4. test_audit_chain_intact                       — verify_audit_chain 通過
  5. test_slo_report_runs                          — slo_report.py 可 import + compute_error_budget 正確

策略：
- 用 auth_client（TestClient + lifespan）
- 用 seed_analysis 模擬已完成的分析（不打 LLM）
- 用 db_session_maker 校驗
- 不依賴 prod compose（這支跑在 dev docker compose 上即可）

跑：cd backend && uv run pytest tests/integration/test_final_smoke.py -v
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════


def _login(client, email: str, password: str) -> tuple[str, str, dict]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    csrf = r.cookies.get("csrf_token") or ""
    return body["data"]["access_token"], csrf, body["data"]


def _auth(access: str, csrf: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {access}"}
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


# ════════════════════════════════════════════════════════
# Smoke 1. admin login
# ════════════════════════════════════════════════════════


async def test_can_login_as_admin(
    auth_client,
    make_test_user,
    flush_rate_limit,
) -> None:
    """admin login → 拿到 access_token + csrf；/auth/me 200。"""
    flush_rate_limit()
    admin, pwd = await make_test_user(
        role="ADMIN",
        must_change=False,
        onboarding_completed=True,
    )

    access, csrf, login_data = _login(auth_client, admin.email, pwd)
    assert access, "access_token 應存在"
    assert csrf, "csrf cookie 應存在"
    assert login_data.get("user", {}).get("role") == "ADMIN"

    me = auth_client.get("/api/v1/auth/me", headers=_auth(access))
    assert me.status_code == 200, me.text
    assert me.json()["data"]["email"] == admin.email


# ════════════════════════════════════════════════════════
# Smoke 2. dashboard 系列 endpoint
# ════════════════════════════════════════════════════════


async def test_dashboard_endpoint_returns_data(
    auth_client,
    make_test_user,
    flush_rate_limit,
) -> None:
    """登入後 watchlist / users/me/quota 應 200 + envelope。"""
    flush_rate_limit()
    user, pwd = await make_test_user(role="VIEWER")
    access, _csrf, _ = _login(auth_client, user.email, pwd)

    # 自選股清單（即使是空陣列也 OK）
    r = auth_client.get("/api/v1/watchlist", headers=_auth(access))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body, "回應必須走 envelope"
    assert isinstance(body["data"], list)

    # 當月 LLM 配額
    r = auth_client.get("/api/v1/users/me/quota", headers=_auth(access))
    assert r.status_code in (200, 404), r.text
    if r.status_code == 200:
        data = r.json()["data"]
        # 結構：monthly_budget_usd / used_usd / remaining_usd 任一存在即可
        assert any(k in data for k in ("monthly_budget_usd", "used_usd", "remaining_usd")), (
            f"quota 結構不符：{data}"
        )


# ════════════════════════════════════════════════════════
# Smoke 3. 完整 analysis workflow（seed-mock）
# ════════════════════════════════════════════════════════


async def test_full_analysis_completes_within_smoke_envelope(
    auth_client,
    make_test_user,
    seed_analysis,
    seed_stocks,
    flush_rate_limit,
) -> None:
    """seed 一筆 completed analysis → 拿得到 signal + report。

    不打 LLM、不跑真實 Celery（PLAN 第 K.3 規定 5 min 內完成的「envelope」）。
    用 seed_analysis 直接造 completed row，驗證 read path。
    """
    flush_rate_limit()
    user, pwd = await make_test_user(role="VIEWER")
    access, _, _ = _login(auth_client, user.email, pwd)

    await seed_stocks(
        [{"symbol": "2330", "market": "TWSE", "name": "台積電", "industry": "半導體"}]
    )
    aid = await seed_analysis(
        user_id=user.id,
        symbol="2330",
        market="TWSE",
        status="completed",
        signal="BUY",
        confidence=Decimal("0.78"),
        report_md="# 2330 分析\n\n## 結論\nBUY，目標價 920。\n",
    )

    r = auth_client.get(f"/api/v1/analysis/{aid}", headers=_auth(access))
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "completed"
    assert body["signal"] == "BUY"
    # 報告內容可能在 report_md / report.markdown / report.summary
    assert any(
        (body.get("report_md") or body.get("report", {}).get("markdown") or "").startswith("# 2330")
        for _ in (None,)
    ), f"report 內容缺失：keys={list(body.keys())}"


# ════════════════════════════════════════════════════════
# Smoke 4. audit chain integrity
# ════════════════════════════════════════════════════════


async def test_audit_chain_intact(
    db_session_maker,
) -> None:
    """verify_audit_chain 在乾淨環境下應 OK（沒有 broken ids）。

    引 app.repos.audit_repo.AuditRepository.verify_chain；
    回 (ok: bool, broken_ids: list[int])。
    """
    from app.repos.audit_repo import AuditRepository

    async with db_session_maker() as s:
        repo = AuditRepository(s)
        ok, broken_ids = await repo.verify_chain(limit=200)

    assert ok is True, f"audit chain 校驗失敗：{broken_ids[:5]}"
    assert isinstance(broken_ids, list)
    assert len(broken_ids) == 0, f"audit chain 出現斷裂：{broken_ids[:5]}"


# ════════════════════════════════════════════════════════
# Smoke 5. slo_report.py 可運行
# ════════════════════════════════════════════════════════


def test_slo_report_runs() -> None:
    """import + compute_error_budget 邏輯正確（已在 P19 test_slo_report.py 詳測）。

    這支 Phase 20 smoke 只負責「最終 sanity」：腳本還能 import + 算 burn rate。
    compute_error_budget 簽名（依 scripts/slo_report.py:197）：
        def compute_error_budget(slo: dict[str, dict[str, Any]]) -> dict[str, float]
    """
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        import slo_report
    finally:
        sys.path.pop(0)

    # 100% 達標 → burn = 0
    burns = slo_report.compute_error_budget({"api_availability": {"target": 0.99, "actual": 1.0}})
    assert burns.get("api_availability") == 0.0, f"100% 達標 burn 應 0，得 {burns}"

    # 99% 達標 → burn ≤ 1.0
    burns = slo_report.compute_error_budget({"api_availability": {"target": 0.99, "actual": 0.99}})
    assert burns.get("api_availability", 999) <= 1.0, f"剛達標 burn ≤ 1，得 {burns}"

    # 90% 達標（嚴重失敗）→ burn > 1 表示已消耗超出預算
    burns = slo_report.compute_error_budget({"api_availability": {"target": 0.99, "actual": 0.90}})
    assert burns.get("api_availability", 0) > 1.0, f"嚴重失敗 burn > 1，得 {burns}"

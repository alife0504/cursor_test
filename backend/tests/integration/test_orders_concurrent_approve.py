"""Phase 11 — /api/v1/orders/* 並發核准測試。

涵蓋：
1. 一般 approve 流程：PENDING → APPROVED + 寫一筆 portfolio_positions
2. 重複 approve 同 order → 第二次 409
3. expected_version 不符 → 409
4. reject 流程
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.order import PendingOrder, PortfolioPosition

pytestmark = pytest.mark.integration


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


async def test_approve_happy_path(
    auth_client,
    make_test_user,
    login_helper,
    seed_stocks,
    seed_analysis,
    seed_pending_order,
    db_session_maker,
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    admin, apwd = await make_test_user(role="ADMIN", must_change=False)
    a_id = await seed_analysis(user_id=admin.id, symbol="2330")
    o_id = await seed_pending_order(user_id=admin.id, analysis_id=a_id, symbol="2330")

    access, csrf = await login_helper(auth_client, admin.email, apwd)
    r = auth_client.post(
        f"/api/v1/orders/{o_id}/approve",
        json={},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "APPROVED"
    assert r.json()["data"]["version"] == 2

    # 驗證 portfolio 已建立
    async with db_session_maker() as s:
        rows = (
            (
                await s.execute(
                    select(PortfolioPosition).where(
                        PortfolioPosition.user_id == admin.id,
                        PortfolioPosition.symbol == "2330",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) >= 1


async def test_double_approve_returns_409(
    auth_client,
    make_test_user,
    login_helper,
    seed_stocks,
    seed_analysis,
    seed_pending_order,
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    admin, apwd = await make_test_user(role="ADMIN", must_change=False)
    a_id = await seed_analysis(user_id=admin.id, symbol="2330")
    o_id = await seed_pending_order(user_id=admin.id, analysis_id=a_id, symbol="2330")

    access, csrf = await login_helper(auth_client, admin.email, apwd)
    r1 = auth_client.post(
        f"/api/v1/orders/{o_id}/approve",
        json={},
        headers=_csrf(access, csrf),
    )
    assert r1.status_code == 200, r1.text

    r2 = auth_client.post(
        f"/api/v1/orders/{o_id}/approve",
        json={},
        headers=_csrf(access, csrf),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "CONFLICT"
    assert "其他人處理" in r2.json()["error"]["message"]


async def test_expected_version_mismatch_returns_409(
    auth_client,
    make_test_user,
    login_helper,
    seed_stocks,
    seed_analysis,
    seed_pending_order,
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    admin, apwd = await make_test_user(role="ADMIN", must_change=False)
    a_id = await seed_analysis(user_id=admin.id, symbol="2330")
    o_id = await seed_pending_order(user_id=admin.id, analysis_id=a_id, symbol="2330")

    access, csrf = await login_helper(auth_client, admin.email, apwd)
    r = auth_client.post(
        f"/api/v1/orders/{o_id}/approve",
        json={"expected_version": 999},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 409, r.text
    assert "版本" in r.json()["error"]["message"]


async def test_reject_flow(
    auth_client,
    make_test_user,
    login_helper,
    seed_stocks,
    seed_analysis,
    seed_pending_order,
    db_session_maker,
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    admin, apwd = await make_test_user(role="ADMIN", must_change=False)
    a_id = await seed_analysis(user_id=admin.id, symbol="2330")
    o_id = await seed_pending_order(user_id=admin.id, analysis_id=a_id, symbol="2330")

    access, csrf = await login_helper(auth_client, admin.email, apwd)
    r = auth_client.post(
        f"/api/v1/orders/{o_id}/reject",
        json={"reason": "風險過高，價格區間不合"},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "REJECTED"

    # 驗 DB
    async with db_session_maker() as s:
        order = (await s.execute(select(PendingOrder).where(PendingOrder.id == o_id))).scalar_one()
        assert order.status == "REJECTED"
        assert order.review_notes == "風險過高，價格區間不合"

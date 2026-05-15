"""Phase 11 — WebSocket /ws/analysis/{id} 整合測試。

涵蓋：
1. 缺 ticket subprotocol → 1008 close
2. 無效 ticket → 1008 close
3. 合法 ticket 但 analysis 屬於他人（非 admin） → 1008 close (IDOR 防護)
4. consume 過的 ticket 重用 → 1008 close
"""

from __future__ import annotations

import pytest
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

pytestmark = pytest.mark.integration


def _issue_ticket(client, access: str, csrf: str) -> str:
    r = client.post(
        "/api/v1/auth/ws-ticket",
        headers={"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["ticket"]


async def test_ws_missing_ticket_closes(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    a_id = await seed_analysis(user_id=user.id, symbol="2330")
    access, _ = await login_helper(auth_client, user.email, pwd)
    _ = access

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        auth_client.websocket_connect(
            f"/api/v1/ws/analysis/{a_id}",
            subprotocols=["tradingagents.v1"],
        ),
    ):
        pass
    assert exc.value.code == 1008


async def test_ws_invalid_ticket_closes(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    a_id = await seed_analysis(user_id=user.id, symbol="2330")
    _, _ = await login_helper(auth_client, user.email, pwd)

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        auth_client.websocket_connect(
            f"/api/v1/ws/analysis/{a_id}",
            subprotocols=["tradingagents.v1", "ticket.invalidtoken1234567890"],
        ),
    ):
        pass
    assert exc.value.code == 1008


async def test_ws_idor_other_user_analysis_forbidden(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    """B 拿 A 的 analysis_id 嘗試 ws subscribe → 1008（IDOR 防護）。"""
    user_a, _ = await make_test_user(role="VIEWER", must_change=False)
    user_b, pwd_b = await make_test_user(role="VIEWER", must_change=False)
    a_id = await seed_analysis(user_id=user_a.id, symbol="2330")

    access_b, csrf_b = await login_helper(auth_client, user_b.email, pwd_b)
    ticket = _issue_ticket(auth_client, access_b, csrf_b)

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        auth_client.websocket_connect(
            f"/api/v1/ws/analysis/{a_id}",
            subprotocols=["tradingagents.v1", f"ticket.{ticket}"],
        ),
    ):
        pass
    assert exc.value.code == 1008


async def test_ws_ticket_consumed_once(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    """同一 ticket 用兩次：第二次必失敗（一次性 ticket，GETDEL）。"""
    user, pwd = await make_test_user(role="ADMIN", must_change=False)
    a_id = await seed_analysis(user_id=user.id, symbol="2330")
    access, csrf = await login_helper(auth_client, user.email, pwd)
    ticket = _issue_ticket(auth_client, access, csrf)

    # 第一次：嘗試連線（admin 看自己的 analysis 應該被接受，但 pubsub.listen() 沒事件會阻塞
    # 所以我們連完立刻關，看是否能 accept handshake；不期待真的收到訊息）
    try:
        with auth_client.websocket_connect(
            f"/api/v1/ws/analysis/{a_id}",
            subprotocols=["tradingagents.v1", f"ticket.{ticket}"],
        ) as ws:
            # 立刻 client-side close
            ws.close()
    except WebSocketDisconnect:
        pass  # server-side close 也視為通過 — ticket 已 consume

    # 第二次：同 ticket → 1008（已 consume）
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        auth_client.websocket_connect(
            f"/api/v1/ws/analysis/{a_id}",
            subprotocols=["tradingagents.v1", f"ticket.{ticket}"],
        ),
    ):
        pass
    assert exc.value.code == 1008


# (For lints: keep imported types referenced)
_ = WebSocketTestSession

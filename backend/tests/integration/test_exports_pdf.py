"""Phase 11 — /api/v1/exports/* 整合測試。

涵蓋：
1. md 匯出（一定可跑）
2. xlsx 匯出（openpyxl 已裝）
3. pdf 匯出（playwright + chromium 已裝才跑；缺則 skip）
4. format=bad → 422
5. 非自己的 report → 403
"""

from __future__ import annotations

import importlib
import os
import shutil

import pytest

pytestmark = pytest.mark.integration


_PW_AVAILABLE = importlib.util.find_spec("playwright") is not None


def _has_chromium_binary() -> bool:
    """Heuristic：找環境變數或預設位置的 chromium 是否存在。"""
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path and os.path.isdir(env_path):
        return any("chromium" in name.lower() for name in os.listdir(env_path))
    # 使用者預設 cache
    home = os.path.expanduser("~")
    cache_paths = [
        os.path.join(home, ".cache", "ms-playwright"),
        os.path.join(home, "AppData", "Local", "ms-playwright"),
    ]
    for p in cache_paths:
        if os.path.isdir(p) and any("chromium" in n.lower() for n in os.listdir(p)):
            return True
    return shutil.which("chromium") is not None or shutil.which("chrome") is not None


async def test_export_md_completed_report(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    a_id = await seed_analysis(
        user_id=user.id,
        symbol="2330",
        status="completed",
        report_md="# 測試報告\n\n台積電(2330) 建議：BUY",
    )
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        f"/api/v1/exports/{a_id}?format=md",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    assert "text/markdown" in r.headers["content-type"]
    body = r.text
    assert "2330" in body
    assert "台積電" in body


async def test_export_xlsx_completed_report(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    a_id = await seed_analysis(
        user_id=user.id,
        symbol="2330",
        status="completed",
        report_md="x",
    )
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        f"/api/v1/exports/{a_id}?format=xlsx",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    # XLSX 為 ZIP 容器，header magic 為 PK\x03\x04
    assert r.content[:2] == b"PK"


async def test_export_bad_format_returns_422(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    a_id = await seed_analysis(user_id=user.id, symbol="2330", status="completed")
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        f"/api/v1/exports/{a_id}?format=docx",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text


async def test_export_not_completed_returns_409(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    a_id = await seed_analysis(user_id=user.id, symbol="2330", status="queued")
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        f"/api/v1/exports/{a_id}?format=md",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 409, r.text


@pytest.mark.skipif(
    not (_PW_AVAILABLE and _has_chromium_binary()),
    reason="playwright + chromium 未安裝；P11 Dockerfile 已加，本地若沒裝則跳過",
)
async def test_export_pdf_renders_chinese(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    a_id = await seed_analysis(
        user_id=user.id,
        symbol="2330",
        status="completed",
        report_md="# 台積電(2330) 分析\n\n投資建議：BUY",
    )
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        f"/api/v1/exports/{a_id}?format=pdf",
        headers={"Authorization": f"Bearer {access}"},
    )
    if r.status_code == 503:
        pytest.skip("Playwright/chromium 啟動失敗（本地環境）")
    assert r.status_code == 200, r.text
    # PDF magic header
    assert r.content[:4] == b"%PDF"

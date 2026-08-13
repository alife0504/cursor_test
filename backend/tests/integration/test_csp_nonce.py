"""Phase 18 — CSP nonce 整合測試（PLAN 19.7 + 第二十七章 P18 P 節）。

驗證：
1. dev 模式 CSP 含 unsafe-eval（給 Next.js HMR）
2. prod 模式 CSP 含 nonce-<value>
3. 每 request nonce 唯一

實作：
- prod 模式靠 settings.CSP_PROD_ENABLED 或 APP_ENV=prod 觸發
- 用 monkeypatch 切換

跑：cd backend && uv run pytest tests/integration/test_csp_nonce.py -v
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.integration


# ════════════════════════════════════════════════════════
# 1. dev CSP 含 unsafe-eval
# ════════════════════════════════════════════════════════


def test_dev_csp_includes_unsafe_eval(auth_client, monkeypatch) -> None:
    """dev 環境（CSP_PROD_ENABLED=False 且 APP_ENV != prod）→ CSP 含 unsafe-eval。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "CSP_PROD_ENABLED", False)
    # APP_ENV 預設是 dev / test
    r = auth_client.get("/health/live")
    csp = r.headers.get("Content-Security-Policy", "")
    assert csp, "Content-Security-Policy header 必須存在"
    assert "unsafe-eval" in csp, f"dev CSP 應含 unsafe-eval，實際：{csp}"
    # dev 模式不該含 nonce
    assert "nonce-" not in csp


# ════════════════════════════════════════════════════════
# 2. prod CSP 含 nonce-<value>
# ════════════════════════════════════════════════════════


def test_prod_csp_includes_nonce(auth_client, monkeypatch) -> None:
    """prod 環境（CSP_PROD_ENABLED=True）→ CSP 含 nonce-<base64url>。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "CSP_PROD_ENABLED", True)
    r = auth_client.get("/health/live")
    csp = r.headers.get("Content-Security-Policy", "")
    assert csp, "CSP header 必須存在"
    assert "nonce-" in csp, f"prod CSP 應含 nonce-<value>，實際：{csp}"
    # prod 不該含 unsafe-eval
    assert "unsafe-eval" not in csp
    # strict-dynamic 應該有
    assert "strict-dynamic" in csp
    # frame-ancestors 'none'
    assert "frame-ancestors 'none'" in csp


# ════════════════════════════════════════════════════════
# 3. 每 request nonce 唯一
# ════════════════════════════════════════════════════════


def test_csp_nonce_unique_per_request(auth_client, monkeypatch) -> None:
    """連續兩個 request 的 nonce 應該不同（防 replay）。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "CSP_PROD_ENABLED", True)
    pat = re.compile(r"nonce-([A-Za-z0-9_-]+)")

    nonces = []
    for _ in range(3):
        r = auth_client.get("/health/live")
        m = pat.search(r.headers.get("Content-Security-Policy", ""))
        assert m, "找不到 nonce 值"
        nonces.append(m.group(1))

    # 全部不同
    assert len(set(nonces)) == len(nonces), f"nonce 應 unique，實際：{nonces}"
    # 長度應該是 token_urlsafe(16) → 22 字元
    assert all(len(n) >= 20 for n in nonces)

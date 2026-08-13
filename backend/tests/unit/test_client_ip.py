"""get_client_ip — 預設不信任代理標頭（防偽造），開啟後依 hops 取對真實 client。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.client_ip import get_client_ip

pytestmark = pytest.mark.unit


class _Req:
    def __init__(
        self, host: str | None = "10.0.0.1", headers: dict[str, str] | None = None
    ) -> None:
        self.client = type("C", (), {"host": host})() if host else None
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}


def _patch(monkeypatch: pytest.MonkeyPatch, *, trust: bool, hops: int = 1) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", trust, raising=False)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", hops, raising=False)


def test_default_ignores_forwarded_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """預設 off：偽造的 X-Forwarded-For 不能繞過 → 一律回直連 peer。"""
    _patch(monkeypatch, trust=False)
    req: Any = _Req(host="10.0.0.1", headers={"X-Forwarded-For": "1.1.1.1"})
    assert get_client_ip(req) == "10.0.0.1"


def test_proxy_on_single_hop_real_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, trust=True, hops=1)
    req: Any = _Req(host="10.0.0.1", headers={"X-Forwarded-For": "5.5.5.5"})
    assert get_client_ip(req) == "5.5.5.5"


def test_proxy_on_skips_spoofed_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """XFF=<偽造>, <真實>；peer=nginx：hops=1 取倒數第二個（nginx 附加的真實 client）。"""
    _patch(monkeypatch, trust=True, hops=1)
    req: Any = _Req(host="10.0.0.1", headers={"X-Forwarded-For": "9.9.9.9, 8.8.8.8"})
    assert get_client_ip(req) == "8.8.8.8"


def test_proxy_on_x_real_ip_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, trust=True, hops=1)
    req: Any = _Req(host="10.0.0.1", headers={"X-Real-IP": "7.7.7.7"})
    assert get_client_ip(req) == "7.7.7.7"


def test_no_client_returns_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, trust=False)
    req: Any = _Req(host=None)
    assert get_client_ip(req) == "0.0.0.0"  # noqa: S104

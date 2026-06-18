"""available_providers() — 依已配置金鑰回報可用 provider（固定順序）。"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.llm import available_providers

pytestmark = pytest.mark.unit


class _FakeSettings:
    def __init__(self, *, g: bool = False, o: bool = False, a: bool = False) -> None:
        self.GOOGLE_API_KEY = SecretStr("k") if g else None
        self.OPENAI_API_KEY = SecretStr("k") if o else None
        self.ANTHROPIC_API_KEY = SecretStr("k") if a else None


def test_only_google() -> None:
    assert available_providers(_FakeSettings(g=True)) == ["google"]  # type: ignore[arg-type]


def test_all_three_keep_order() -> None:
    out = available_providers(_FakeSettings(g=True, o=True, a=True))  # type: ignore[arg-type]
    assert out == ["google", "openai", "anthropic"]


def test_none_configured() -> None:
    assert available_providers(_FakeSettings()) == []  # type: ignore[arg-type]

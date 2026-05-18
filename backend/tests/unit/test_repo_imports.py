"""驗證關鍵套件可被 import（uv sync 安裝是否完整）。

這是 v7.0 Phase 1 的測試雛形（4/5）。
後續 Phase 會新增更多 import 驗證。
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.unit


# Phase 1 階段必須能 import 的套件清單
P1_REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic_settings",
    "structlog",
    "httpx",
    "tenacity",
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "redis",
    "jose",  # python-jose
    "passlib",
    "email_validator",
]


@pytest.mark.parametrize("module_name", P1_REQUIRED_MODULES)
def test_p1_module_can_be_imported(module_name: str) -> None:
    """Phase 1 必需的套件全部可 import。"""
    importlib.import_module(module_name)


def test_python_version_311() -> None:
    """Python 必須是 3.11.x（依第 6.1 章 pin）。"""
    import sys

    assert sys.version_info[:2] == (3, 11), f"Python 必須是 3.11.x，目前 {sys.version_info[:3]}"


def test_pydantic_v2_imports() -> None:
    """Pydantic 必須是 v2（依 ADR / v6.1 章）。"""
    import pydantic

    major = int(pydantic.VERSION.split(".")[0])
    assert major >= 2, f"Pydantic 必須 ≥ 2，目前 {pydantic.VERSION}"

"""Phase 1 骨架測試：驗證後端目錄結構齊全。

這是 v7.0 Phase 1 的測試雛形之一（共 5 個）。
後續 Phase 會新增實際業務邏輯測試。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# 從 backend/tests/unit/test_skeleton.py 往上 3 層 = backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
PROJECT_ROOT = BACKEND_ROOT.parent


# ───────────────────────── 測試 ─────────────────────────


def test_backend_app_directory_exists() -> None:
    """app/ 目錄必須存在。"""
    assert APP_ROOT.is_dir(), f"backend/app/ 不存在: {APP_ROOT}"


def test_backend_subdirectories_complete() -> None:
    """app/ 下必須有所有 v7.0 規範子目錄（依第二十二章）。"""
    required = [
        "api/v1",
        "core",
        "repos",
        "services",
        "domain",
        "models",
        "schemas",
        "agents/analysts",
        "agents/researchers",
        "agents/managers",
        "agents/tools/tw",
        "agents/tools/us",
        "data_sources/tw",
        "data_sources/us",
        "data_sources/base",
        "llm",
        "workers",
        "notifications",
        "exports",
    ]
    missing = [d for d in required if not (APP_ROOT / d).is_dir()]
    assert not missing, f"backend/app/ 下缺少子目錄：{missing}"


def test_legacy_directory_exists_and_isolated() -> None:
    """legacy/ 必須存在；根目錄不可有原版檔（tradingagents/ 等）。"""
    legacy = PROJECT_ROOT / "legacy"
    assert legacy.is_dir(), "legacy/ 目錄不存在"
    # 根目錄不該有原版套件
    forbidden_at_root = ["tradingagents", "cli"]
    leaked = [name for name in forbidden_at_root if (PROJECT_ROOT / name).exists()]
    assert not leaked, f"以下原版項目仍在根目錄（應在 legacy/）：{leaked}"


def test_engineering_docs_present() -> None:
    """工程規範文件必須齊全。"""
    docs_required = [
        PROJECT_ROOT / "docs" / "engineering-standards.md",
        PROJECT_ROOT / "docs" / "setup.md",
        PROJECT_ROOT / "docs" / "contributing.md",
        PROJECT_ROOT / "docs" / "phase_progress.md",
    ]
    missing = [str(p.relative_to(PROJECT_ROOT)) for p in docs_required if not p.is_file()]
    assert not missing, f"缺少文件：{missing}"


def test_pre_commit_and_secrets_baseline_present() -> None:
    """pre-commit + detect-secrets baseline 必須存在。"""
    pc = PROJECT_ROOT / ".pre-commit-config.yaml"
    baseline = PROJECT_ROOT / ".secrets.baseline"
    assert pc.is_file(), ".pre-commit-config.yaml 不存在"
    assert baseline.is_file(), ".secrets.baseline 不存在"

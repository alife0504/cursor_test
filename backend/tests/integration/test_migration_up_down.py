"""Alembic upgrade / downgrade 雙向測試。

驗證每個 migration 都正確寫 downgrade，且 full 雙向 cycle 不會卡。

注意：
- 此測試會破壞性 down/up；放最後跑（pytest 預設 alphabetical 順序，
  test_migration_up_down 排在 test_schema 之後）。
- 結束時保證 schema 在 head（避免污染下個測試）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration


_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


def _config() -> Config:
    """讀 backend/alembic.ini（同 CLI alembic 用）。"""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    return cfg


def test_upgrade_head_succeeds() -> None:
    """alembic upgrade head 應成功（idempotent）。"""
    cfg = _config()
    command.upgrade(cfg, "head")


def test_downgrade_one_succeeds_and_back() -> None:
    """alembic downgrade -1 後再 upgrade head，schema 回到 head。"""
    cfg = _config()
    try:
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")
    finally:
        # 保險：確保 head（即使前面失敗也補一刀）
        command.upgrade(cfg, "head")


def test_full_downgrade_to_base_succeeds() -> None:
    """alembic downgrade base 後再 upgrade head，schema 完整重建。"""
    cfg = _config()
    try:
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")

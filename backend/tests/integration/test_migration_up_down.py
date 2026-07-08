"""Alembic upgrade / downgrade 雙向測試。

驗證每個 migration 都正確寫 downgrade，且 full 雙向 cycle 不會卡。

⚠️ 破壞性警告（2026-07-02 事故教訓）：
- downgrade base 會 DROP 所有表 → **連同資料一起消失**。此測試若對著
  「有資料的 dev DB」跑，會把 stock_list / users / 分析歷史全部清空
  （已實際發生過一次，靠 seed 腳本重建）。
- 因此 downgrade 類測試預設 skip，必須明確設
  `MIGRATION_TEST_ALLOW_DESTRUCTIVE=1` 才會執行（CI 的拋棄式 DB 再開）。
- upgrade head 是 idempotent、無破壞性，不受此 gate 影響。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_DESTRUCTIVE_OK = os.environ.get("MIGRATION_TEST_ALLOW_DESTRUCTIVE") == "1"
_SKIP_REASON = (
    "破壞性 downgrade 測試：會清空目標 DB 的所有資料。"
    "只能對拋棄式 DB 跑，需明確設 MIGRATION_TEST_ALLOW_DESTRUCTIVE=1"
)


_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


def _config() -> Config:
    """讀 backend/alembic.ini（同 CLI alembic 用）。"""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    return cfg


def test_upgrade_head_succeeds() -> None:
    """alembic upgrade head 應成功（idempotent；無破壞性，不需 gate）。"""
    cfg = _config()
    command.upgrade(cfg, "head")


@pytest.mark.skipif(not _DESTRUCTIVE_OK, reason=_SKIP_REASON)
def test_downgrade_one_succeeds_and_back() -> None:
    """alembic downgrade -1 後再 upgrade head，schema 回到 head。"""
    cfg = _config()
    try:
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")
    finally:
        # 保險：確保 head（即使前面失敗也補一刀）
        command.upgrade(cfg, "head")


@pytest.mark.skipif(not _DESTRUCTIVE_OK, reason=_SKIP_REASON)
def test_full_downgrade_to_base_succeeds() -> None:
    """alembic downgrade base 後再 upgrade head，schema 完整重建。"""
    cfg = _config()
    try:
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")

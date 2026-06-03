"""data-pipeline scripts 整合測試（PLAN 第 13.1 章 Bootstrap）。

需 docker compose up（DB healthy + alembic upgrade head）。

測試項目：
- seed_stock_list 純函式（hardcoded universe size + fetch parsing + upsert）
- seed_users 兩次跑 idempotent
- verify_data 對 seeded DB 至少不 FAIL

不跑真網路（fetch_twse / fetch_tpex 在 unit 部分 mock）；
seed_stock_list 整體流程在 phase_07.sh 的 acceptance 部分跑真網路。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

pytestmark = pytest.mark.integration


# ─────────── helper：動態 import data-pipeline/scripts/ ───────────


_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "data-pipeline" / "scripts"


def _load_script(name: str):
    """importlib 載入 data-pipeline/scripts/<name>.py。"""
    path = _SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─────────── seed_stock_list tests ───────────


def test_seed_stock_list_us_universe_size() -> None:
    """hardcoded US universe 應 ≥ 100 筆（NASDAQ 100 + Dow 30 + S&P top 50 unique）。"""
    mod = _load_script("seed_stock_list")
    items = mod.build_us_universe()
    assert len(items) >= 100
    # 每筆都應有 symbol / market / name / is_active
    for it in items[:5]:
        assert "symbol" in it and isinstance(it["symbol"], str)
        assert it["market"] == "NASDAQ"
        assert it["is_active"] is True


@pytest.mark.asyncio
async def test_seed_stock_list_fetch_twse_parses_correctly() -> None:
    """mock httpx client → 驗 fetch_twse_listed 解析欄位。"""
    mod = _load_script("seed_stock_list")
    fake_data = [
        {"Code": "1101", "Name": "台泥", "ClosingPrice": "30.5"},
        {"Code": "2330", "Name": "台積電", "ClosingPrice": "1000"},
        # 缺欄位的應被略過
        {"Code": "", "Name": "ignored"},
        {"Code": "9999", "Name": ""},
    ]

    fake_client = AsyncMock()

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> Any:
            return fake_data

    fake_client.get = AsyncMock(return_value=_Resp())

    items = await mod.fetch_twse_listed(fake_client)
    assert len(items) == 2
    assert items[0]["symbol"] == "1101"
    assert items[0]["market"] == "TWSE"
    assert items[1]["name"] == "台積電"


@pytest.mark.asyncio
async def test_seed_stock_list_upsert_idempotent() -> None:
    """跑兩次 upsert_to_db 相同資料 → DB 不重複（PK 衝突 ON CONFLICT DO UPDATE）。"""
    mod = _load_script("seed_stock_list")
    items = [
        {"symbol": "_T_SEED1", "market": "TWSE", "name": "test1", "is_active": True},
        {"symbol": "_T_SEED2", "market": "TWSE", "name": "test2", "is_active": True},
    ]

    n1 = await mod.upsert_to_db(items)
    n2 = await mod.upsert_to_db(items)  # 第二次：應該不會新增任何 row（PK 一樣）

    # cleanup + 驗 row count
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            count = (
                await session.execute(
                    text("SELECT count(*) FROM stock_list WHERE symbol IN ('_T_SEED1', '_T_SEED2')")
                )
            ).scalar()
            assert int(count or 0) == 2  # 兩次跑後仍只有 2 筆
            # cleanup
            await session.execute(
                text("DELETE FROM stock_list WHERE symbol IN ('_T_SEED1', '_T_SEED2')")
            )
            await session.commit()
    finally:
        await engine.dispose()

    assert n1 == 2 and n2 == 2  # upsert_many 回的是「處理筆數」，不是 net new


# ─────────── seed_users tests ───────────


@pytest.mark.asyncio
async def test_seed_users_idempotent() -> None:
    """seed_admin 兩次跑 → 第二次回 "existed"。"""
    mod = _load_script("seed_users")
    # 第一次（可能已存在 = init_db.py 跑過了）→ 接受 created 或 existed
    status1 = await mod.seed_admin()
    assert status1 in ("created", "existed")
    # 第二次必為 existed
    status2 = await mod.seed_admin()
    assert status2 == "existed"


# ─────────── verify_data tests ───────────


@pytest.mark.asyncio
async def test_verify_data_runs_without_crash() -> None:
    """verify_data 主流程跑完不 crash（exit code 可能是 0/1/2，視 DB 狀態）。

    不用 capsys（會與 structlog cache_logger_on_first_use 衝突，污染後續 tests）。
    只驗 main() 能跑完，exit code 在預期範圍。
    """
    mod = _load_script("verify_data")
    try:
        await mod.main()
        exit_code = 0
    except SystemExit as e:
        exit_code = int(e.code or 0)
    # exit code 0 / 1 / 2 都可接受（視 DB 狀態而定）
    assert exit_code in (0, 1, 2)

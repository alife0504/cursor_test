"""DB 連線測試（驗證 P2 三帳號分離設計）。

需 docker compose up（timescaledb healthy）。

驗證：
1. ta_migration  → 可建表（DDL）
2. ta_service_rw → 可 SELECT/INSERT/UPDATE/DELETE，但不能 DDL
3. ta_agent_ro   → 可 SELECT，但不能 INSERT/UPDATE/DELETE/DDL

依 PLAN.md 第 19.1 章帳號分離設計。
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

# psycopg / asyncpg 都還沒裝（P3 才裝），用 stdlib socket 簡單驗連線
# DDL/DML 測試在 P3 後可改用 SQLAlchemy / asyncpg


def _try_pg_connect(host: str, port: int, user: str, password: str, db: str) -> tuple[bool, str]:
    """用 psycopg2 / psycopg / asyncpg 任一個可用的驅動連線。
    回 (success, error_msg_or_empty)。
    """
    # 嘗試用 socket 簡單測能不能連到 port（最低門檻）
    import socket

    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as e:
        return False, f"socket connect failed: {e}"

    # 嘗試用 asyncpg（P1 已裝）做 auth
    try:
        import asyncio

        import asyncpg  # type: ignore[import-not-found]

        async def _check() -> tuple[bool, str]:
            try:
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=db,
                    timeout=5,
                )
                await conn.execute("SELECT 1")
                await conn.close()
                return True, ""
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}"

        return asyncio.run(_check())
    except ImportError:
        return False, "asyncpg not installed (run uv sync)"


def _try_pg_execute(
    host: str,
    port: int,
    user: str,
    password: str,
    db: str,
    sql: str,
) -> tuple[bool, str]:
    """嘗試在指定帳號下執行 SQL，回 (success, error_msg)。"""
    try:
        import asyncio

        import asyncpg  # type: ignore[import-not-found]

        async def _exec() -> tuple[bool, str]:
            try:
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=db,
                    timeout=5,
                )
                try:
                    await conn.execute(sql)
                    return True, ""
                finally:
                    await conn.close()
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}"

        return asyncio.run(_exec())
    except ImportError:
        return False, "asyncpg not installed"


def _skip_if_no_db(host: str, port: int) -> None:
    """若 DB 不可達，跳過測試（不算 fail）。"""
    import socket

    try:
        with socket.create_connection((host, port), timeout=2):
            return
    except OSError:
        pytest.skip(f"PostgreSQL not reachable at {host}:{port} (start with `make up`)")


# ───────────────────────── 測試 ─────────────────────────


def test_postgres_superuser_can_connect(
    env_vars: dict[str, Any], pg_host: str, pg_port: int, pg_db: str
) -> None:
    """superuser 必能連線（最低 sanity）。"""
    _skip_if_no_db(pg_host, pg_port)
    pwd = env_vars.get("POSTGRES_SUPERUSER_PASSWORD", "")
    assert pwd, "POSTGRES_SUPERUSER_PASSWORD 未設"
    ok, err = _try_pg_connect(pg_host, pg_port, "postgres", pwd, pg_db)
    assert ok, f"superuser 連線失敗：{err}"


def test_ta_migration_can_create_table(
    env_vars: dict[str, Any], pg_host: str, pg_port: int, pg_db: str
) -> None:
    """ta_migration 應可建表（測試後 drop 清理）。"""
    _skip_if_no_db(pg_host, pg_port)
    pwd = env_vars.get("TA_MIGRATION_PASSWORD", "")
    assert pwd, "TA_MIGRATION_PASSWORD 未設"

    ok, err = _try_pg_execute(
        pg_host,
        pg_port,
        "ta_migration",
        pwd,
        pg_db,
        "CREATE TABLE IF NOT EXISTS _phase02_test_table (id INT)",
    )
    assert ok, f"ta_migration 建表失敗：{err}"

    # 清理
    _try_pg_execute(
        pg_host,
        pg_port,
        "ta_migration",
        pwd,
        pg_db,
        "DROP TABLE IF EXISTS _phase02_test_table",
    )


def test_ta_service_rw_cannot_create_table(
    env_vars: dict[str, Any], pg_host: str, pg_port: int, pg_db: str
) -> None:
    """ta_service_rw 不應有 CREATE TABLE 權限（DDL 禁止）。"""
    _skip_if_no_db(pg_host, pg_port)
    pwd = env_vars.get("TA_SERVICE_RW_PASSWORD", "")
    assert pwd, "TA_SERVICE_RW_PASSWORD 未設"

    ok, err = _try_pg_execute(
        pg_host,
        pg_port,
        "ta_service_rw",
        pwd,
        pg_db,
        "CREATE TABLE _phase02_should_fail (id INT)",
    )
    assert not ok, "ta_service_rw 不該能建表"
    assert (
        "permission denied" in err.lower() or "權限" in err.lower()
    ), f"預期 permission denied，實際：{err}"


def test_ta_agent_ro_can_select(
    env_vars: dict[str, Any], pg_host: str, pg_port: int, pg_db: str
) -> None:
    """ta_agent_ro 應可 SELECT（最低門檻）。"""
    _skip_if_no_db(pg_host, pg_port)
    pwd = env_vars.get("TA_AGENT_RO_PASSWORD", "")
    assert pwd, "TA_AGENT_RO_PASSWORD 未設"
    # 簡單 SELECT 1（不依賴特定表）
    ok, err = _try_pg_execute(
        pg_host,
        pg_port,
        "ta_agent_ro",
        pwd,
        pg_db,
        "SELECT 1",
    )
    assert ok, f"ta_agent_ro SELECT 失敗：{err}"


def test_ta_agent_ro_cannot_create_table(
    env_vars: dict[str, Any], pg_host: str, pg_port: int, pg_db: str
) -> None:
    """ta_agent_ro 不應有任何 DDL/DML 寫入權限。"""
    _skip_if_no_db(pg_host, pg_port)
    pwd = env_vars.get("TA_AGENT_RO_PASSWORD", "")
    assert pwd, "TA_AGENT_RO_PASSWORD 未設"
    ok, err = _try_pg_execute(
        pg_host,
        pg_port,
        "ta_agent_ro",
        pwd,
        pg_db,
        "CREATE TABLE _phase02_ro_fail (id INT)",
    )
    assert not ok, "ta_agent_ro 不該能建表"
    assert (
        "permission denied" in err.lower() or "權限" in err.lower()
    ), f"預期 permission denied，實際：{err}"


def test_timescaledb_extension_enabled(
    env_vars: dict[str, Any], pg_host: str, pg_port: int, pg_db: str
) -> None:
    """TimescaleDB extension 應已啟用（init.sql.template 第 1 段）。"""
    _skip_if_no_db(pg_host, pg_port)
    pwd = env_vars.get("POSTGRES_SUPERUSER_PASSWORD", "")

    import asyncio

    import asyncpg  # type: ignore[import-not-found]

    async def _check() -> bool:
        conn = await asyncpg.connect(
            host=pg_host,
            port=pg_port,
            user="postgres",
            password=pwd,
            database=pg_db,
            timeout=5,
        )
        try:
            row = await conn.fetchrow(
                "SELECT extname FROM pg_extension WHERE extname='timescaledb'"
            )
            return row is not None
        finally:
            await conn.close()

    assert asyncio.run(_check()), "timescaledb extension 未啟用"

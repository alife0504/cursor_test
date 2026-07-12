"""一次性 DB 初始化腳本：

1. 跑 `alembic upgrade head`（透過 subprocess，借用 backend/ 環境）
2. 確保 Qdrant 7 個 collections 存在（idempotent）
3. 建立第一個 admin 帳號（must_change_password=TRUE）

用法：
    cd C:\\Projects\\TradingAgents
    uv run --project backend python data-pipeline/scripts/init_db.py

注意：
- 預設讀 ADMIN_EMAIL / ADMIN_INITIAL_PASSWORD（從 .env），不從 CLI argv
- 重複跑安全：alembic upgrade head 跳過已套用、Qdrant collection 已存在跳過、
  users 已有同 email 跳過 INSERT
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

# 將 backend/ 加 sys.path 才能 import app.*
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.logging_config import configure_logging, get_logger  # noqa: E402

configure_logging()
logger = get_logger(__name__)


def step_1_run_alembic_upgrade() -> None:
    """跑 `alembic upgrade head`。"""
    logger.info("init_db.step_1.alembic_upgrade.start")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error(
            "init_db.alembic_upgrade.failed",
            stderr=result.stderr,
            stdout=result.stdout,
        )
        raise SystemExit(f"alembic upgrade head failed:\n{result.stderr}")
    logger.info("init_db.step_1.alembic_upgrade.done")


async def step_2_ensure_qdrant_collections() -> None:
    """確保 Qdrant 7 個 collections 存在。"""
    from app.core.qdrant_init import ensure_collections

    logger.info("init_db.step_2.qdrant_collections.start")
    results = await ensure_collections()
    logger.info("init_db.step_2.qdrant_collections.done", results=results)


async def step_3_create_initial_admin() -> str:
    """建立 ADMIN_EMAIL 對應的第一個 admin 帳號（idempotent）。

    Returns:
        "created" | "existed"
    """
    import bcrypt
    from sqlalchemy import text

    from app.core.database import get_migration_engine

    logger.info("init_db.step_3.admin.start", email=settings.ADMIN_EMAIL)

    email = str(settings.ADMIN_EMAIL).lower()
    password = settings.ADMIN_INITIAL_PASSWORD.get_secret_value()
    # 直接用 bcrypt（避開 passlib + bcrypt 4.x 的 wrap-bug 偵測誤觸發）
    # cost=12 對齊 PLAN 19.1
    password_bytes = password.encode("utf-8")[:72]  # bcrypt 上限 72 bytes
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")

    engine = get_migration_engine()
    async with engine.begin() as conn:
        existed = (
            await conn.execute(
                text("SELECT id FROM users WHERE LOWER(email) = :email"),
                {"email": email},
            )
        ).scalar()
        if existed is not None:
            logger.info("init_db.step_3.admin.already_exists", email=email)
            return "existed"

        await conn.execute(
            text(
                """
                INSERT INTO users (
                    email, password_hash, full_name, role,
                    preferred_timezone, preferred_language,
                    onboarding_completed, must_change_password,
                    is_active
                ) VALUES (
                    :email, :password_hash, :full_name, 'ADMIN',
                    :tz, :lang,
                    true, true,
                    true
                )
                """
            ),
            {
                "email": email,
                "password_hash": password_hash,
                "full_name": "Admin",
                "tz": settings.DEFAULT_TIMEZONE,
                "lang": settings.DEFAULT_LANG,
            },
        )

    logger.info("init_db.step_3.admin.created", email=email)
    return "created"


async def main() -> None:
    """主程序。"""
    logger.info("init_db.start")

    # Step 1：alembic（sync subprocess）
    step_1_run_alembic_upgrade()

    # Step 2：Qdrant collections
    await step_2_ensure_qdrant_collections()

    # Step 3：admin
    admin_status = await step_3_create_initial_admin()

    # 收尾 dispose
    from app.core.database import dispose_db_connections
    from app.core.qdrant_client import dispose_qdrant_client

    await dispose_db_connections()
    await dispose_qdrant_client()

    logger.info(
        "init_db.done",
        admin=admin_status,
        email=str(settings.ADMIN_EMAIL),
    )
    # 用 ASCII 避免 Windows cp950 console 編碼問題
    sys.stdout.write(
        f"\n[OK] init_db done: admin={admin_status}, "
        f"email={settings.ADMIN_EMAIL}\n"
        "[WARN] 第一次登入後請立即修改密碼 (must_change_password=TRUE)\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())

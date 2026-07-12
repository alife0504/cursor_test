"""seed_users.py — 建立第一個 admin 帳號（PLAN 第 13.4 章 onboarding）。

從 .env 讀 ADMIN_EMAIL / ADMIN_INITIAL_PASSWORD，bcrypt hash 後 INSERT users，
must_change_password=TRUE。已存在則 skip（idempotent）。

用法：
    cd C:\\Projects\\TradingAgents
    uv run --project backend python data-pipeline/scripts/seed_users.py

注意：與 init_db.py 的 step 3 邏輯一致，但抽出來做獨立腳本，方便：
- 已 init 完，但 admin 被誤刪需要重建
- 切換 ADMIN_EMAIL 後新增第二個 admin
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 將 backend/ 加 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.logging_config import configure_logging, get_logger  # noqa: E402

configure_logging()
logger = get_logger(__name__)


async def seed_admin() -> str:
    """建立 ADMIN_EMAIL 對應的 admin 帳號（idempotent）。

    Returns:
        "created" | "existed"
    """
    import bcrypt
    from sqlalchemy import text

    from app.core.database import dispose_db_connections, get_migration_engine

    email = str(settings.ADMIN_EMAIL).lower()
    password = settings.ADMIN_INITIAL_PASSWORD.get_secret_value()
    # bcrypt 上限 72 bytes
    password_bytes = password.encode("utf-8")[:72]
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")

    engine = get_migration_engine()  # 用 ta_migration（DDL + DML 帳號）
    try:
        async with engine.begin() as conn:
            existed = (
                await conn.execute(
                    text("SELECT id FROM users WHERE LOWER(email) = :email"),
                    {"email": email},
                )
            ).scalar()
            if existed is not None:
                logger.info("seed_users.admin.existed email=%s", email)
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
        logger.info("seed_users.admin.created email=%s", email)
        return "created"
    finally:
        await dispose_db_connections()


async def main() -> None:
    logger.info("seed_users.start email=%s", settings.ADMIN_EMAIL)
    status = await seed_admin()
    sys.stdout.write(
        f"\n[OK] seed_users done: admin={status}, email={settings.ADMIN_EMAIL}\n"
    )
    if status == "created":
        sys.stdout.write(
            "[WARN] must_change_password=TRUE — 第一次登入後請立即修改密碼\n"
        )
    sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())

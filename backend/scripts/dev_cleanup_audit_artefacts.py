"""v1.0.1 — 開發環境用：清除 audit_logs 的測試殘留，恢復 audit_integrity SLO。

**僅限 dev / test 環境**。Production 直接 exit 1。

背景：
PLAN 第 9.2 章 SLO `audit_integrity` 期望 100%；但 tests/security/test_audit_chain_tampering.py
會故意 UPDATE / DELETE audit_logs 來測「能否偵測篡改」，跑完後若 fixture 沒乾淨清回，
SLO 就會看到 broken_id（v1.0 結案報告中觀察到 535, 559）。

策略（v1.0.1 採用「全部 TRUNCATE 重新開始」最乾淨）：
- 若 APP_ENV not in {dev, test} → exit 1
- 在執行前印出將會刪除的 row 數
- `--dry-run` 只報告不執行
- `--yes` 跳過互動確認

使用：
    cd backend
    uv run python scripts/dev_cleanup_audit_artefacts.py --dry-run
    uv run python scripts/dev_cleanup_audit_artefacts.py --yes

預期效果：
- audit_logs row 全部清空
- 下一次寫入 audit 時 prev_hash 從零開始
- `make slo-report` 的 audit_integrity = 100%
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 把 backend/ 加入 sys.path（這個檔案放在 backend/scripts/ 下，要往上跳一層）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))


async def _run(dry_run: bool, force: bool) -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.config import settings
    from app.core.database import get_rw_engine

    if settings.APP_ENV not in {"dev", "test"}:
        print(
            f"[FAIL] 拒絕在 APP_ENV={settings.APP_ENV} 執行（本腳本只允許 dev / test）",
            file=sys.stderr,
        )
        return 1

    engine = get_rw_engine()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with maker() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM audit_logs"))).scalar_one() or 0
        if total == 0:
            print("[OK] audit_logs 已為空，無事可做")
            return 0

        print(f"[INFO] APP_ENV={settings.APP_ENV}")
        print(f"[INFO] audit_logs 目前有 {total} 筆 row")

        if dry_run:
            print("[DRY-RUN] 不執行，使用 --yes 真正清除")
            return 0

        if not force:
            try:
                resp = input(f"[CONFIRM] 真的要 TRUNCATE audit_logs（{total} 筆）？輸入 yes 確認：")
            except EOFError:
                print("[FAIL] 無互動環境，請使用 --yes", file=sys.stderr)
                return 1
            if resp.strip().lower() != "yes":
                print("[ABORT] 已取消")
                return 0

        await session.execute(text("TRUNCATE TABLE audit_logs"))
        await session.commit()
        print(f"[OK] 已清空 audit_logs（移除 {total} 筆）")
        print("[INFO] 之後新寫入的 audit 從 prev_hash=000...0 重新開始")
        print("[INFO] 跑 'make slo-report' 應看到 audit_integrity = 100%")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="清除 dev/test 環境的 audit_logs 測試殘留（v1.0.1）。"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只顯示將清除的 row 數，不真正執行",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳過互動確認（CI / 自動化用）",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args.dry_run, args.yes))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

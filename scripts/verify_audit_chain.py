"""Phase 9 — 獨立 CLI：完整重算 audit_logs hash chain。

用法：
    cd backend && uv run python ../scripts/verify_audit_chain.py
    cd backend && uv run python ../scripts/verify_audit_chain.py --since 2026-05-01
    cd backend && uv run python ../scripts/verify_audit_chain.py --since 2026-05-01 --limit 1000

輸出：
    exit 0 + "✅ Audit chain integrity verified"   chain 完整
    exit 1 + "❌ Audit chain BROKEN at IDs: [...]" chain 有斷裂

依 PLAN 19.6 章。獨立 CLI 用 ta_agent_ro 連線（read-only，不會意外寫入）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 把 backend/ 加入 sys.path
_BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND_ROOT))


async def _run(since_str: str | None, limit: int | None) -> int:
    """執行 verify；回 exit code。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.database import get_ro_engine
    from app.repos.audit_repo import AuditRepository

    since: datetime | None = None
    if since_str:
        try:
            since = datetime.fromisoformat(since_str)
        except ValueError:
            print(f"❌ --since 格式錯誤：{since_str}（請用 ISO 8601，如 2026-05-01）")
            return 2

    engine = get_ro_engine()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        repo = AuditRepository(session)
        ok, broken = await repo.verify_chain(since=since, limit=limit)

    if ok:
        print("[OK] Audit chain integrity verified")
        return 0
    else:
        print(f"[FAIL] Audit chain BROKEN at IDs: {broken[:50]}")
        if len(broken) > 50:
            print(f"   ... another {len(broken) - 50} broken rows")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify audit_logs hash chain integrity")
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="只驗證該 timestamp 之後（ISO 8601 格式，如 2026-05-01）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多檢查 N 筆（除錯用）",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args.since, args.limit))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

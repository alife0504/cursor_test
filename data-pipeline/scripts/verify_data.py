"""verify_data.py — 驗證資料完整性（PLAN 第 13.1 章 Bootstrap 流程驗證）。

驗收：
- stock_list >= 1500
- 至少 1 支股票 stock_prices >= 200 row
- audit_logs row count（P9 才會有真正 chain verify，P7 暫只看 row 數）
- 印出每張關鍵表 row count

退出碼：
- 0：全部通過（"OK" 標記）
- 1：有 WARN（少於門檻但 > 0）
- 2：有 FAIL（核心表為 0 / 連線失敗）

用法：
    cd C:\\Projects\\TradingAgents
    uv run --project backend python data-pipeline/scripts/verify_data.py
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

from app.core.logging_config import configure_logging, get_logger  # noqa: E402

configure_logging()
logger = get_logger(__name__)


# 關鍵表（核心 = 為 0 算 FAIL；輔助 = 為 0 算 WARN；附屬 = 只印 row 數不檢查）
_CORE_TABLES = ["stock_list", "users"]
_AUX_TABLES = ["stock_prices", "audit_logs"]
_INFO_TABLES = [
    "stock_info",
    "news_metadata",
    "announcements",
    "monthly_revenue",
    "institutional_trading",
    "margin_trading",
    "financial_statements",
    "celery_dead_letters",
    "idempotency_keys",
    "user_sessions",
    "pending_orders",
    "analysis_reports",
]


async def count_rows(session, table: str) -> int:
    """count 失敗時自動 rollback，避免 transaction abort 影響後續 query。"""
    from sqlalchemy import text

    try:
        return int(
            (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar() or 0
        )
    except Exception as exc:
        logger.warning("verify_data.count.failed table=%s err=%s", table, exc)
        # 重要：失敗後 rollback transaction，否則後續所有查詢都會被 aborted
        try:
            await session.rollback()
        except Exception:  # pragma: no cover
            pass
        return -1


async def main() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.database import dispose_db_connections, get_ro_engine

    engine = get_ro_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)

    fails: list[str] = []
    warns: list[str] = []

    try:
        async with sm() as session:
            sys.stdout.write("\n=== verify_data ===\n\n")

            # ─── Core 表（為 0 算 FAIL） ───
            sys.stdout.write("[Core tables]\n")
            for table in _CORE_TABLES:
                n = await count_rows(session, table)
                status = "OK" if n > 0 else "FAIL"
                if n <= 0:
                    fails.append(f"{table} = {n}")
                sys.stdout.write(f"  {table:<30} {n:>8}  {status}\n")

            # ─── stock_list >= 1500 ───
            n_stocks = await count_rows(session, "stock_list")
            if n_stocks < 1500:
                msg = f"stock_list = {n_stocks} < 1500"
                if n_stocks < 100:
                    fails.append(msg)
                else:
                    warns.append(msg)

            # ─── 至少 1 支股票 stock_prices >= 200 row ───
            sys.stdout.write("\n[Backfill check]\n")
            try:
                row = (
                    await session.execute(
                        text(
                            "SELECT symbol, count(*) AS n "
                            "FROM stock_prices "
                            "GROUP BY symbol "
                            "ORDER BY n DESC "
                            "LIMIT 5"
                        )
                    )
                ).all()
            except Exception as exc:
                logger.warning("verify_data.stock_prices_query_failed err=%s", exc)
                row = []

            if not row:
                warns.append("stock_prices 為空（請先跑 backfill）")
                sys.stdout.write("  WARN: stock_prices 沒有任何 row\n")
            else:
                top = row[0]
                top_sym = top.symbol
                top_n = int(top.n)
                sys.stdout.write(f"  Top symbol: {top_sym} = {top_n} rows\n")
                if top_n < 200:
                    warns.append(
                        f"最大筆數 stock_prices.{top_sym} = {top_n} < 200（建議至少 1 支 >= 200）"
                    )
                else:
                    sys.stdout.write(f"  OK: {top_sym} 有 {top_n} 筆 >= 200\n")
                # 印 top 5
                for r in row:
                    sys.stdout.write(f"    {r.symbol:<10} {int(r.n):>6} rows\n")

            # ─── Aux 表（為 0 算 WARN） ───
            sys.stdout.write("\n[Aux tables]\n")
            for table in _AUX_TABLES:
                n = await count_rows(session, table)
                status = "OK" if n > 0 else "WARN"
                if n == 0:
                    warns.append(f"{table} 為空")
                sys.stdout.write(f"  {table:<30} {n:>8}  {status}\n")

            # ─── Info 表（只印） ───
            sys.stdout.write("\n[Info tables]\n")
            for table in _INFO_TABLES:
                n = await count_rows(session, table)
                sys.stdout.write(f"  {table:<30} {n:>8}\n")

            # ─── audit_logs hash chain（P7 stub） ───
            sys.stdout.write("\n[Audit chain] (P9 將升級為真實 verify)\n")
            n_audit = await count_rows(session, "audit_logs")
            sys.stdout.write(f"  audit_logs row count = {n_audit}\n")
            sys.stdout.write("  STUB: chain verify 在 P9 audit_repo 完成後啟用\n")

    finally:
        await dispose_db_connections()

    # ─── 結論 ───
    sys.stdout.write("\n=== verify_data result ===\n")
    if fails:
        sys.stdout.write("FAIL:\n")
        for f in fails:
            sys.stdout.write(f"  - {f}\n")
    if warns:
        sys.stdout.write("WARN:\n")
        for w in warns:
            sys.stdout.write(f"  - {w}\n")
    if not fails and not warns:
        sys.stdout.write("PASS: all checks OK\n")
    elif not fails:
        sys.stdout.write("OK with WARN\n")
    else:
        sys.stdout.write("FAIL\n")
    sys.stdout.flush()

    if fails:
        raise SystemExit(2)
    if warns:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

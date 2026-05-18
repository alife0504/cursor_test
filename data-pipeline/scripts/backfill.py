"""backfill.py — 回填指定股票 N 年 OHLCV（PLAN 第 13.1 章 step 6）。

不走 celery（直接同步呼叫 DataPipelineService），跑進度條方便人工監控。

用法：
    cd C:\\Projects\\TradingAgents

    # 單支
    uv run --project backend python data-pipeline/scripts/backfill.py \\
        --region TW --symbol 2330 --years 1

    # 全部 active TW
    uv run --project backend python data-pipeline/scripts/backfill.py \\
        --region TW --symbol all --years 1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill OHLCV (PLAN 13.1 step 6)")
    p.add_argument("--region", choices=["TW", "US"], required=True, help="市場區域")
    p.add_argument(
        "--symbol",
        required=True,
        help="股票代碼（如 2330 / AAPL），或 'all' 表示該 region 全部 active",
    )
    p.add_argument("--years", type=int, default=1, help="回填年數（1-10），default 1")
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="若 symbol=all，限制最多處理幾支（0 = 不限）",
    )
    return p.parse_args()


async def list_active_symbols(region: str, limit: int) -> list[tuple[str, str]]:
    """從 stock_list 撈 active symbols。"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.database import dispose_db_connections, get_ro_engine
    from app.models.stock import StockList

    if region == "TW":
        markets = ["TWSE", "TPEX"]
    else:
        markets = ["NASDAQ", "NYSE", "AMEX"]

    engine = get_ro_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            stmt = (
                select(StockList.symbol, StockList.market)
                .where(
                    StockList.is_active.is_(True),
                    StockList.market.in_(markets),
                )
                .order_by(StockList.symbol)
            )
            if limit > 0:
                stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).all()
        return [(r.symbol, r.market) for r in rows]
    finally:
        await dispose_db_connections()


async def backfill_one(
    symbol: str, market: str, years: int
) -> tuple[bool, int, str | None]:
    """回填單支。回 (success, written, error_msg)。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.database import dispose_db_connections, get_rw_engine
    from app.data_sources.tw import get_tw_sources
    from app.data_sources.us import get_us_sources
    from app.services.data_pipeline_service import DataPipelineService

    sources = (
        get_tw_sources(settings) if market in ("TWSE", "TPEX") else get_us_sources(settings)
    )

    end = datetime.now(UTC).date()
    start = end - timedelta(days=years * 365 + 30)  # 多抓 30 天 buffer

    engine = get_rw_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            n = await service.sync_ohlcv(symbol, market, start, end)
        return True, int(n), None
    except Exception as exc:
        logger.warning("backfill.one.failed symbol=%s err=%s", symbol, exc)
        return False, 0, str(exc)
    finally:
        await dispose_db_connections()


async def main() -> None:
    args = parse_args()
    logger.info(
        "backfill.start region=%s symbol=%s years=%d limit=%d",
        args.region, args.symbol, args.years, args.limit,
    )

    # 1. 解析 symbol list
    if args.symbol.lower() == "all":
        targets = await list_active_symbols(args.region, args.limit)
        if not targets:
            sys.stderr.write(
                f"[ERROR] {args.region} 沒有 active symbols。請先跑 seed_stock_list\n"
            )
            raise SystemExit(2)
    else:
        # 單支 — 推測 market（TW: TWSE 4 碼 / TPEX 4 碼難分，預設 TWSE）
        market = "TWSE" if args.region == "TW" else "NASDAQ"
        targets = [(args.symbol, market)]

    # 2. 跑 backfill
    try:
        from tqdm import tqdm  # type: ignore[import-untyped]
    except ImportError:
        # tqdm 缺失 → 用簡易 print
        def tqdm(iterable, **_kwargs):  # type: ignore[no-redef]
            return iterable

    results: list[tuple[str, str, bool, int, str | None]] = []
    for sym, mkt in tqdm(targets, desc="backfill", unit="sym"):
        ok, n, err = await backfill_one(sym, mkt, args.years)
        results.append((sym, mkt, ok, n, err))

    # 3. 統計
    success = [r for r in results if r[2]]
    failed = [r for r in results if not r[2]]
    total_rows = sum(r[3] for r in success)

    sys.stdout.write(
        "\n[OK] backfill done\n"
        f"  Total: {len(results)}\n"
        f"  Success: {len(success)} (rows written: {total_rows})\n"
        f"  Failed: {len(failed)}\n"
    )
    if failed:
        sys.stdout.write("\n失敗清單（重試指引：手動跑 backfill --symbol XXX）：\n")
        for sym, mkt, _ok, _n, err in failed[:20]:
            sys.stdout.write(f"  - {sym} ({mkt}): {err}\n")
        if len(failed) > 20:
            sys.stdout.write(f"  ... 另外 {len(failed) - 20} 支\n")
    sys.stdout.flush()

    if failed and len(success) == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""從 FinMind 本地庫「一次性大量」回填 margin_trading / stock_info（唯讀來源）。

為什麼要 bulk 而非 per-symbol fan-out：
    per-symbol fan-out 對 2,375 檔各開一條 asyncpg 連線到 fm-postgres，並發會撐爆
    fm-postgres 的 max_connections → finmind_local 大量失敗 → 落到限流的 FinMind API →
    也失敗（實測 margin 只回補到 381 檔）。bulk 只用「一條連線、一次查詢」讀整張表，
    再一次 upsert，快且不會連線爆掉。近 1~2 日（本地庫未涵蓋）由每日排程的小 fan-out 補。

用法（從 backend/ 執行）：
    cd backend && PYTHONPATH=. uv run python scripts/backfill_from_local_bulk.py [margin|info|all]
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings


async def _local_conn():
    import asyncpg

    pw = settings.FINMIND_LOCAL_PASSWORD
    return await asyncpg.connect(
        host=settings.FINMIND_LOCAL_HOST,
        port=settings.FINMIND_LOCAL_PORT,
        user=settings.FINMIND_LOCAL_USER,
        password=pw.get_secret_value() if pw else None,
        database=settings.FINMIND_LOCAL_DB,
        timeout=30,
    )


async def _active_symbols(session) -> set[str]:
    rows = await session.execute(
        text("SELECT symbol FROM stock_list WHERE is_active AND market IN ('TWSE','TPEX')")
    )
    return {r[0] for r in rows.all()}


_MARGIN_UPSERT = text(
    """
    INSERT INTO margin_trading
        (symbol, date, margin_buy, margin_sell, margin_balance, margin_quota,
         short_buy, short_sell, short_balance, short_quota, source)
    VALUES (:symbol, :date, :margin_buy, :margin_sell, :margin_balance, :margin_quota,
            :short_buy, :short_sell, :short_balance, :short_quota, 'finmind_local')
    ON CONFLICT (symbol, date) DO UPDATE SET
        margin_buy=EXCLUDED.margin_buy, margin_sell=EXCLUDED.margin_sell,
        margin_balance=EXCLUDED.margin_balance, margin_quota=EXCLUDED.margin_quota,
        short_buy=EXCLUDED.short_buy, short_sell=EXCLUDED.short_sell,
        short_balance=EXCLUDED.short_balance, short_quota=EXCLUDED.short_quota,
        source=EXCLUDED.source
    """
)


async def backfill_margin(session, days: int) -> int:
    active = await _active_symbols(session)
    conn = await _local_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT stock_id, date,
                   COALESCE(NULLIF(trim("MarginPurchaseBuy"::text),'')::numeric,0)::bigint          AS margin_buy,
                   COALESCE(NULLIF(trim("MarginPurchaseSell"::text),'')::numeric,0)::bigint         AS margin_sell,
                   COALESCE(NULLIF(trim("MarginPurchaseTodayBalance"::text),'')::numeric,0)::bigint AS margin_balance,
                   COALESCE(NULLIF(trim("MarginPurchaseLimit"::text),'')::numeric,0)::bigint        AS margin_quota,
                   COALESCE(NULLIF(trim("ShortSaleBuy"::text),'')::numeric,0)::bigint               AS short_buy,
                   COALESCE(NULLIF(trim("ShortSaleSell"::text),'')::numeric,0)::bigint              AS short_sell,
                   COALESCE(NULLIF(trim("ShortSaleTodayBalance"::text),'')::numeric,0)::bigint      AS short_balance,
                   COALESCE(NULLIF(trim("ShortSaleLimit"::text),'')::numeric,0)::bigint             AS short_quota
            FROM bronze.taiwan_stock_margin_purchase_short_sale
            WHERE date >= (CURRENT_DATE - $1::int)
            """,
            days,
        )
    finally:
        await conn.close()

    written = 0
    batch: list[dict[str, Any]] = []
    for r in rows:
        if r["stock_id"] not in active:
            continue
        batch.append(dict(r) | {"symbol": r["stock_id"]})
        if len(batch) >= 5000:
            await session.execute(_MARGIN_UPSERT, batch)
            written += len(batch)
            batch = []
    if batch:
        await session.execute(_MARGIN_UPSERT, batch)
        written += len(batch)
    await session.commit()
    return written


_INFO_UPSERT = text(
    """
    INSERT INTO stock_info (symbol, full_name, sector)
    VALUES (:symbol, :full_name, :sector)
    ON CONFLICT (symbol) DO UPDATE SET
        full_name=COALESCE(EXCLUDED.full_name, stock_info.full_name),
        sector=COALESCE(EXCLUDED.sector, stock_info.sector)
    """
)


async def backfill_info(session) -> int:
    active = await _active_symbols(session)
    conn = await _local_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (stock_id) stock_id, stock_name, industry_category
            FROM bronze.taiwan_stock_info
            ORDER BY stock_id, date DESC
            """
        )
    finally:
        await conn.close()

    batch = [
        {"symbol": r["stock_id"], "full_name": r["stock_name"], "sector": r["industry_category"]}
        for r in rows
        if r["stock_id"] in active
    ]
    if not batch:
        return 0
    await session.execute(_INFO_UPSERT, batch)
    await session.commit()
    return len(batch)


async def backfill_margin_api_gap(session, days: int) -> int:
    """用 FinMind API（不帶 data_id → 單日全市場）補近日缺口。

    本地庫盤後入庫落後時（近 1~2 週只有零星幾檔），用「每天一次請求」把近日全市場補齊。
    只寫 active 個股；來源標 finmind（與 finmind_local 區分）。
    """
    from datetime import date, timedelta

    from app.core.config import settings as _s
    from app.data_sources.tw.finmind_source import FinMindSource

    active = await _active_symbols(session)
    src = FinMindSource(_s)
    # 今天往前推 days 天；用台北日界（UTC+8）避免剛過午夜時抓不到當日
    end = date.today()
    start = end - timedelta(days=days)
    rows = await src.fetch_all_margin(start, end)

    written = 0
    batch: list[dict[str, Any]] = []
    for r in rows:
        if r["symbol"] not in active:
            continue
        batch.append({**r, "source": "finmind"})
        if len(batch) >= 5000:
            await session.execute(_MARGIN_UPSERT_API, batch)
            written += len(batch)
            batch = []
    if batch:
        await session.execute(_MARGIN_UPSERT_API, batch)
        written += len(batch)
    await session.commit()
    return written


_MARGIN_UPSERT_API = text(
    """
    INSERT INTO margin_trading
        (symbol, date, margin_buy, margin_sell, margin_balance, margin_quota,
         short_buy, short_sell, short_balance, short_quota, source)
    VALUES (:symbol, :date, :margin_buy, :margin_sell, :margin_balance, :margin_quota,
            :short_buy, :short_sell, :short_balance, :short_quota, :source)
    ON CONFLICT (symbol, date) DO UPDATE SET
        margin_buy=EXCLUDED.margin_buy, margin_sell=EXCLUDED.margin_sell,
        margin_balance=EXCLUDED.margin_balance, margin_quota=EXCLUDED.margin_quota,
        short_buy=EXCLUDED.short_buy, short_sell=EXCLUDED.short_sell,
        short_balance=EXCLUDED.short_balance, short_quota=EXCLUDED.short_quota,
        source=EXCLUDED.source
    """
)


async def main(which: str, days: int) -> None:
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            if which in ("margin", "all"):
                n = await backfill_margin(session, days)
                print(f"[done] margin_trading（本地庫）upsert {n} 列")
            if which in ("margin-api", "all"):
                n = await backfill_margin_api_gap(session, 14)
                print(f"[done] margin_trading（API 近日缺口）upsert {n} 列")
            if which in ("info", "all"):
                n = await backfill_info(session)
                print(f"[done] stock_info upsert {n} 檔")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    asyncio.run(main(which, days))

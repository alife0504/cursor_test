"""從 FinMind 本地庫回填 stock_list.industry（PIT 期限分類的前置資料）。

為什麼需要：
    實測 stock_list.industry 有 99.7% 為 NULL（2,401 檔中僅 8 檔有值），連富邦金/中信金/
    兆豐金都是空的。而財報法定期限**依申報人類別而異**（證交法 §36 / 特殊適用範圍辦法 §3）：
    金融保險業 Q2 是「終了後二個月」= 8/31，一般公司是 45 日 = 8/14。
    沒有產業別就無法分類 → 一律套 GENERAL → 對金融股寫入**過早**的期限 → 偷看未來 18 天。

資料來源：FinMind 本地庫 bronze.taiwan_stock_info.industry_category（**唯讀**，不寫入該庫）。

用法（從 backend/ 執行）：
    cd backend && PYTHONPATH=. uv run python scripts/backfill_industry.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings


async def _fetch_finmind_industries() -> list[dict[str, Any]]:
    """從 FinMind 本地庫讀 stock_id → industry_category（唯讀）。"""
    import asyncpg

    pw = settings.FINMIND_LOCAL_PASSWORD
    conn = await asyncpg.connect(
        host=settings.FINMIND_LOCAL_HOST,
        port=settings.FINMIND_LOCAL_PORT,
        user=settings.FINMIND_LOCAL_USER,
        password=pw.get_secret_value() if pw else None,
        database=settings.FINMIND_LOCAL_DB,
        timeout=15,
    )
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (stock_id) stock_id, industry_category
            FROM bronze.taiwan_stock_info
            WHERE industry_category IS NOT NULL AND industry_category <> ''
            ORDER BY stock_id, date DESC
            """
        )
    finally:
        await conn.close()
    return [{"symbol": r["stock_id"], "industry": r["industry_category"]} for r in rows]


_UPDATE = text(
    """
    UPDATE stock_list SET industry = :industry
     WHERE symbol = :symbol AND industry IS DISTINCT FROM :industry
    """
).bindparams(bindparam("industry"), bindparam("symbol"))


async def main(dry_run: bool) -> None:
    pairs = await _fetch_finmind_industries()
    print(f"FinMind 本地庫提供 {len(pairs)} 檔的產業分類")
    fin = [p for p in pairs if "金融" in p["industry"] or "保險" in p["industry"]]
    print(f"  其中金融保險類 {len(fin)} 檔（這些的 Q2 期限是 8/31 而非 8/14）")

    if dry_run:
        for p in fin[:5]:
            print(f"  [dry-run] {p['symbol']} → {p['industry']}")
        print("dry-run：未寫入")
        return

    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            updated = 0
            for p in pairs:
                res = await session.execute(_UPDATE, p)
                updated += res.rowcount or 0
            await session.commit()
            print(f"[done] stock_list.industry 更新 {updated} 列")

            cov = (
                await session.execute(
                    text(
                        """
                        SELECT count(*) AS total, count(industry) AS filled
                        FROM stock_list WHERE is_active AND market IN ('TWSE','TPEX')
                        """
                    )
                )
            ).one()
            print(f"驗收：active 台股 {cov.total} 檔，其中 {cov.filled} 檔有產業別")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印不寫")
    asyncio.run(main(ap.parse_args().dry_run))

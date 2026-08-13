"""清除「已停用**個股/權證**」在資料表裡的殘留 OHLCV / 三大法人資料。

為什麼要獨立成腳本（而非隨手一句 DELETE）：
    直覺會寫 `DELETE ... WHERE NOT is_active`，但**指數（TAIEX/TPEX）在 stock_list 是
    market='OTHER' 且 is_active=false**（刻意的：不讓指數混進個股搜尋，見 seed_index_ohlcv）。
    那句 DELETE 會把指數價格一起刪掉，害儀錶板大盤變空——我踩過這個坑。
    故本腳本**明確排除 OTHER 市場**，只清 TWSE/TPEX 裡被停用的權證殘留。

用法（從 backend/ 執行）：
    cd backend && PYTHONPATH=. uv run python scripts/purge_inactive_market_data.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

# 只清「一般個股市場」裡被停用者。**排除 OTHER**（指數在此，且刻意 is_active=false）。
_TARGET_MARKETS = ("TWSE", "TPEX", "NYSE", "NASDAQ", "AMEX")

_COUNT_SQL = {
    "stock_prices": text(
        """
        SELECT count(*) FROM stock_prices p JOIN stock_list s ON s.symbol = p.symbol
         WHERE NOT s.is_active AND s.market = ANY(:markets)
        """
    ),
    "institutional_trading": text(
        """
        SELECT count(*) FROM institutional_trading i JOIN stock_list s ON s.symbol = i.symbol
         WHERE NOT s.is_active AND s.market = ANY(:markets)
        """
    ),
}
_DELETE_SQL = {
    "stock_prices": text(
        """
        DELETE FROM stock_prices p USING stock_list s
         WHERE s.symbol = p.symbol AND NOT s.is_active AND s.market = ANY(:markets)
        """
    ),
    "institutional_trading": text(
        """
        DELETE FROM institutional_trading i USING stock_list s
         WHERE s.symbol = i.symbol AND NOT s.is_active AND s.market = ANY(:markets)
        """
    ),
}


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    params = {"markets": list(_TARGET_MARKETS)}
    try:
        async with sm() as session:
            for table in ("stock_prices", "institutional_trading"):
                n = (await session.execute(_COUNT_SQL[table], params)).scalar_one()
                if dry_run:
                    print(f"  [dry-run] {table}: 將刪除 {n} 列")
                    continue
                await session.execute(_DELETE_SQL[table], params)
                print(f"  {table}: 刪除 {n} 列")
            if dry_run:
                print("dry-run：未寫入")
                return
            await session.commit()

            # 驗收：指數必須還在（沒被誤刪）
            idx = (
                await session.execute(
                    text("SELECT count(*) FROM stock_prices WHERE symbol IN ('TAIEX', 'TPEX')")
                )
            ).scalar_one()
            print(f"驗收：指數 OHLCV 仍存在 {idx} 列（>0 表示未誤刪指數）")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印不刪")
    asyncio.run(main(ap.parse_args().dry_run))

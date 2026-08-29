"""stock_prices 歷史深度回填 —— 從 finmind_local(bronze) 補足回測/命中率所需的長歷史。

## 為什麼需要
backtest_service / statistics_service 讀 app 自己的 stock_prices（retention 5 年），但該表
只從 app 上線後累積（實測僅 ~4 個月）→ 選「1 年」被截斷、Sharpe/最大回撤在 4 個月上算不準。
bronze.taiwan_stock_price 有 1994~今、14M+ 列可回填。

## 安全設計（對共用的 fm-postgres 絕對穩定）
- **唯讀** bronze（Postgres MVCC，讀不鎖 finmind-platform 的寫）。
- **低並發** semaphore（預設 6）：fm-postgres 同時最多 N 個讀連線，負載極小、可隨時 Ctrl-C 中止。
- 走**既有已測** DataPipelineService.sync_ohlcv（finmind_local 讀 bronze + adj JOIN），
  correctness 與每日同步完全一致；ON CONFLICT idempotent，可重跑。
- 歷史視窗的合併對舊日期由 finmind_local 完整涵蓋 → 不打 finmind API（僅最新幾日可能補 API，量小）。

用法：
    PYTHONPATH=. uv run python scripts/backfill_stock_prices_history.py [--years 5] [--concurrency 6] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.data_sources.base import DataKind
from app.data_sources.tw import get_tw_sources
from app.repos.ohlcv_repo import OHLCVRepository


async def _active_tw_symbols(sm: async_sessionmaker, limit: int | None) -> list[tuple[str, str]]:
    async with sm() as s:
        sql = (
            "SELECT symbol, market FROM stock_list "
            "WHERE market IN ('TWSE','TPEX') AND is_active ORDER BY symbol"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = (await s.execute(text(sql))).all()
    return [(r[0], r[1]) for r in rows]


async def main(years: int, concurrency: int, limit: int | None) -> None:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=365 * years + 5)
    engine = create_async_engine(
        settings.postgres_dsn_rw, pool_size=concurrency + 2, max_overflow=2
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)

    # **直接用 finmind_local（讀 bronze），繞過 DataPipelineService 的多源合併**：
    # 合併會在「日曆未達今日」時續打 finmind API 抓整個 5 年窗（極慢 + 大量 API 負載）。
    # 歷史回填只需權威的 bronze，故直接呼叫 finmind_local.fetch_ohlcv，零 API、對 fm-postgres
    # 僅低並發唯讀。最新幾日的補齊交給每日排程（已修的 merge）。
    ohlcv_sources = get_tw_sources(settings).get(DataKind.OHLCV, [])
    local = next((s for s in ohlcv_sources if s.name == "finmind_local"), None)
    if local is None:
        raise RuntimeError("找不到 finmind_local source（FINMIND_LOCAL_ENABLED 是否為 true？）")

    symbols = await _active_tw_symbols(sm, limit)
    total = len(symbols)
    print(
        f"回填 {total} 檔台股，視窗 {start} ~ {end}（{years} 年），並發 {concurrency}，來源=finmind_local"
    )

    sem = asyncio.Semaphore(concurrency)
    done = 0
    written_total = 0
    failed: list[str] = []
    lock = asyncio.Lock()

    async def _one(symbol: str, market: str) -> None:
        nonlocal done, written_total
        async with sem:
            try:
                df = await local.fetch_ohlcv(symbol, start, end)
                if df is not None and not df.empty:
                    rows = []
                    for r in df.to_dict(orient="records"):
                        if r.get("date") is None:
                            continue
                        r["symbol"] = symbol
                        rows.append(r)
                    if rows:
                        async with sm() as session:
                            repo = OHLCVRepository(session)
                            n = await repo.upsert_many(rows, source="finmind_local", commit=True)
                        async with lock:
                            written_total += int(n)
            except Exception as exc:  # 單檔失敗不影響整體
                async with lock:
                    failed.append(f"{symbol}:{type(exc).__name__}")
            finally:
                async with lock:
                    done += 1
                    if done % 100 == 0 or done == total:
                        print(
                            f"  進度 {done}/{total}，累計寫入 {written_total} 列，失敗 {len(failed)}"
                        )

    await asyncio.gather(*[_one(sym, mkt) for sym, mkt in symbols])
    await engine.dispose()
    print(f"[done] {done}/{total} 檔，寫入 {written_total} 列，失敗 {len(failed)}")
    if failed:
        print("  失敗樣本:", failed[:20])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    asyncio.run(main(args.years, args.concurrency, args.limit))

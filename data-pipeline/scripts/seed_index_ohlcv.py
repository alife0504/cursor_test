"""seed_index_ohlcv.py — 為大盤指數（TAIEX 加權 / TPEX 櫃買）寫入 OHLCV（dev/demo）。

背景（v1.0.2）：
- Dashboard 的 KpiRow / MarketIndexMiniChart 會抓 `useOhlcv("TAIEX")` / `useOhlcv("TPEX")`
  畫 sparkline 與顯示指數值。但 v1.0 從未把大盤指數資料寫進 `stock_prices`，
  且 `stock_prices.symbol` 有 FK → `stock_list.symbol`，所以必須先建立指數的 stock_list entry。
- 本腳本提供 dev / demo 用的合成指數序列（deterministic random walk，標 `source="dev-seed"`
  方便區分與清除），讓本機 dashboard 立刻「活起來」、不再全是「—」。

⚠️ 這是 **dev/demo 資料**，不是真實行情。正式環境的真實大盤回填（TWSE/TPEX 指數歷史）
   屬 v1.1 infra（見 PLAN 第 33 章 / CHANGELOG v1.1 待辦）。本腳本強制 APP_ENV != prod。

清除 dev-seed 資料：
    DELETE FROM stock_prices WHERE source = 'dev-seed';

用法：
    cd C:\\Projects\\TradingAgents
    uv run --project backend python data-pipeline/scripts/seed_index_ohlcv.py --days 120 --yes
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.logging_config import configure_logging, get_logger  # noqa: E402

configure_logging()
logger = get_logger(__name__)

# 指數定義：symbol / 中文名 / 起始點位（合理量級，純 demo）
_INDICES: list[tuple[str, str, float]] = [
    ("TAIEX", "加權指數", 23000.0),
    ("TPEX", "櫃買指數", 270.0),
]

_SEED_SOURCE = "dev-seed"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed 大盤指數 OHLCV（dev/demo）")
    p.add_argument("--days", type=int, default=120, help="回填交易日數（default 120）")
    p.add_argument("--yes", action="store_true", help="略過確認直接寫入")
    return p.parse_args()


def _gen_series(base: float, days: int, *, symbol: str) -> list[dict]:
    """deterministic random walk（依 symbol 設 seed，可重現）。回最舊→最新。"""
    rng = random.Random(f"taindex-{symbol}")  # noqa: S311 — demo 用，非密碼學
    out: list[dict] = []
    price = base
    today = datetime.now(UTC).date()
    # 從 days 個「日曆日」前往回推，跳過週末（粗略模擬交易日）
    d = today - timedelta(days=int(days * 1.45))
    while d <= today and len(out) < days:
        if d.weekday() < 5:  # 一~五
            drift = rng.uniform(-0.012, 0.013)  # 每日 ±1.2%
            open_p = price
            close_p = max(1.0, price * (1 + drift))
            high_p = max(open_p, close_p) * (1 + rng.uniform(0, 0.004))
            low_p = min(open_p, close_p) * (1 - rng.uniform(0, 0.004))
            vol = rng.randint(2_000_000, 6_000_000) * 1000
            out.append(
                {
                    "date": d,
                    "open": Decimal(f"{open_p:.2f}"),
                    "high": Decimal(f"{high_p:.2f}"),
                    "low": Decimal(f"{low_p:.2f}"),
                    "close": Decimal(f"{close_p:.2f}"),
                    "volume": vol,
                }
            )
            price = close_p
        d += timedelta(days=1)
    return out


async def _seed(days: int) -> int:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.database import dispose_db_connections, get_rw_engine
    from app.models.price import StockPrice
    from app.models.stock import StockList

    written = 0
    engine = get_rw_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            for symbol, name, base in _INDICES:
                # 1. 確保 stock_list 有指數 entry（market=OTHER / is_active=False，不進個股搜尋）
                await session.execute(
                    pg_insert(StockList)
                    .values(
                        symbol=symbol,
                        market="OTHER",
                        name=name,
                        short_name=name,
                        industry="大盤指數",
                        is_active=False,
                    )
                    .on_conflict_do_update(
                        index_elements=["symbol"],
                        set_={"name": name, "industry": "大盤指數"},
                    )
                )
                # 2. upsert OHLCV
                rows = _gen_series(base, days, symbol=symbol)
                for r in rows:
                    await session.execute(
                        pg_insert(StockPrice)
                        .values(symbol=symbol, source=_SEED_SOURCE, **r)
                        .on_conflict_do_update(
                            index_elements=["symbol", "date"],
                            set_={
                                "open": r["open"],
                                "high": r["high"],
                                "low": r["low"],
                                "close": r["close"],
                                "volume": r["volume"],
                                "source": _SEED_SOURCE,
                            },
                        )
                    )
                written += len(rows)
                logger.info("seed_index.done", symbol=symbol, rows=len(rows))
            await session.commit()
    finally:
        await dispose_db_connections()
    return written


def main() -> None:
    env = (settings.APP_ENV or "dev").lower()
    if env not in {"dev", "test"}:
        sys.stderr.write(
            f"[ERROR] 拒絕在 APP_ENV={env} 寫入 dev-seed 指數資料（只允許 dev / test）。\n"
        )
        raise SystemExit(2)

    args = parse_args()
    if not args.yes:
        sys.stdout.write(
            f"將寫入 {len(_INDICES)} 個指數 × {args.days} 交易日 OHLCV（source=dev-seed，APP_ENV={env}）。\n"
            "這是 demo 資料，非真實行情。加 --yes 確認執行。\n"
        )
        return

    n = asyncio.run(_seed(args.days))
    sys.stdout.write(f"[OK] seed_index_ohlcv 完成：寫入 {n} 筆（source=dev-seed）。\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

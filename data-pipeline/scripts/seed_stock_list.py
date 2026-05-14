"""seed_stock_list.py — 初始化 stock_list 表（PLAN 第 13.1 章 step 3）。

抓取來源：
- TWSE 上市：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL
- TPEX 上櫃：https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes
- US：hardcoded NASDAQ 100 + Dow Jones 30（S&P 500 top 50 補 cushion）

驗收：總筆數應 ≥ 1500（PLAN /health/seeded 門檻為 100，此腳本給更高保護量）。

用法：
    cd C:\\Projects\\TradingAgents
    uv run --project backend python data-pipeline/scripts/seed_stock_list.py

重複跑安全（StockRepository.upsert_many 走 ON CONFLICT (symbol) DO UPDATE）。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx

# 將 backend/ 加 sys.path 才能 import app.*
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.logging_config import configure_logging, get_logger  # noqa: E402

configure_logging()
logger = get_logger(__name__)


# ─────────── Hardcoded US universe ───────────
# 寫死的 NASDAQ 100 + Dow 30（S&P 500 涵蓋大部分）。
# 不從 wikipedia 動態抓 — wikipedia HTML 結構常變、CI 不穩。
# 每年手動更新一次（PLAN 第 7 章 honest tradeoffs）。

_DOW_30 = [
    "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
    "DOW", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT",
]

_NASDAQ_100 = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "ALGN", "AMAT",
    "AMD", "AMGN", "AMZN", "ANSS", "ASML", "AVGO", "AZN", "BIIB", "BKNG",
    "BKR", "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CMCSA", "COST", "CPRT",
    "CRWD", "CSCO", "CSGP", "CSX", "CTAS", "CTSH", "DASH", "DDOG", "DLTR",
    "DXCM", "EA", "EXC", "FANG", "FAST", "FTNT", "GEHC", "GFS", "GILD",
    "GOOG", "GOOGL", "HON", "IDXX", "ILMN", "INTC", "INTU", "ISRG", "KDP",
    "KHC", "KLAC", "LIN", "LRCX", "LULU", "MAR", "MCHP", "MDB", "MDLZ",
    "MELI", "META", "MNST", "MRNA", "MRVL", "MSFT", "MU", "NFLX", "NVDA",
    "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP",
    "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS", "TEAM", "TMUS",
    "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBA", "WBD", "WDAY",
    "XEL", "ZS",
]

# 額外幾支大型 S&P 500（避免太接近 1500 邊界）
_SP500_EXTRA = [
    "JNJ", "JPM", "V", "PG", "UNH", "HD", "MA", "BAC", "PFE", "DIS",
    "XOM", "CVX", "WMT", "KO", "MCD", "NKE", "T", "VZ", "WFC", "MS",
    "GS", "BLK", "AXP", "C", "USB", "TFC", "PNC", "SCHW", "CB", "ICE",
    "F", "GM", "DAL", "UAL", "AAL", "LUV", "BA", "LMT", "RTX", "GD",
    "CAT", "DE", "HON", "MMM", "GE", "EMR", "ETN", "ROK", "CMI", "PCAR",
]

# 取 union 並排序
_US_SYMBOLS = sorted(set(_DOW_30 + _NASDAQ_100 + _SP500_EXTRA))


# ─────────── HTTP 抓取 helpers ───────────


async def _fetch_json(client: httpx.AsyncClient, url: str, *, retries: int = 3) -> Any:
    """重試版本 GET JSON。"""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = await client.get(url, timeout=httpx.Timeout(30.0, connect=10.0))
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc
            wait = 2**attempt
            logger.warning(
                "seed_stock_list.fetch_retry url=%s attempt=%d wait=%ds err=%s",
                url, attempt, wait, exc,
            )
            await asyncio.sleep(wait)
    assert last_exc is not None
    raise last_exc


async def fetch_twse_listed(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """TWSE 上市股票（OpenAPI v1 STOCK_DAY_AVG_ALL）。"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
    try:
        data = await _fetch_json(client, url)
    except Exception as e:
        logger.error("seed_stock_list.twse_failed err=%s", e)
        return []

    items: list[dict[str, Any]] = []
    for row in data:
        code = (row.get("Code") or "").strip()
        name = (row.get("Name") or "").strip()
        if not code or not name:
            continue
        items.append({"symbol": code, "market": "TWSE", "name": name, "is_active": True})
    logger.info("seed_stock_list.twse fetched=%d", len(items))
    return items


async def fetch_tpex_listed(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """TPEX 上櫃股票（OpenAPI v1 tpex_mainboard_daily_close_quotes）。"""
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
    try:
        data = await _fetch_json(client, url)
    except Exception as e:
        logger.error("seed_stock_list.tpex_failed err=%s", e)
        return []

    items: list[dict[str, Any]] = []
    for row in data:
        # TPEX 不同 endpoint 欄位名稱有差異，container 容錯多種 key
        code = (
            row.get("SecuritiesCompanyCode")
            or row.get("CompanyCode")
            or row.get("Code")
            or ""
        ).strip()
        name = (row.get("CompanyName") or row.get("Name") or "").strip()
        if not code or not name:
            continue
        items.append({"symbol": code, "market": "TPEX", "name": name, "is_active": True})
    logger.info("seed_stock_list.tpex fetched=%d", len(items))
    return items


def build_us_universe() -> list[dict[str, Any]]:
    """美股 hardcoded universe。market 統一給 NASDAQ（後續 P10 可細分 NYSE/NASDAQ）。"""
    items: list[dict[str, Any]] = []
    for sym in _US_SYMBOLS:
        items.append(
            {
                "symbol": sym,
                "market": "NASDAQ",  # 簡化：先全標 NASDAQ，後續補 NYSE/AMEX 細分
                "name": sym,  # name 用 symbol 占位，後續 stock_info seeder 會補真正名稱
                "is_active": True,
            }
        )
    logger.info("seed_stock_list.us hardcoded=%d", len(items))
    return items


# ─────────── upsert ───────────


async def upsert_to_db(items: list[dict[str, Any]]) -> int:
    """寫入 stock_list 表（ON CONFLICT (symbol) DO UPDATE）。"""
    from app.core.database import dispose_db_connections, get_rw_engine
    from app.repos.stock_repo import StockRepository
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = get_rw_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)

    n = 0
    try:
        async with sm() as session:
            repo = StockRepository(session)
            # 分批 upsert（避免單次 INSERT VALUES 太大被 PG planner 拒）
            batch_size = 500
            for i in range(0, len(items), batch_size):
                chunk = items[i : i + batch_size]
                n += await repo.upsert_many(chunk, commit=False)
            await session.commit()
    finally:
        await dispose_db_connections()
    return n


# ─────────── 主程序 ───────────


async def main() -> None:
    """抓三個來源 → 合併 → upsert → 驗證。"""
    logger.info("seed_stock_list.start")

    async with httpx.AsyncClient(
        headers={"User-Agent": "TradingAgents-TW seed_stock_list/1.0"}
    ) as client:
        twse_items, tpex_items = await asyncio.gather(
            fetch_twse_listed(client),
            fetch_tpex_listed(client),
        )

    us_items = build_us_universe()

    # 合併（symbol 去重 — 以最後寫入者為準）
    all_items_by_symbol: dict[str, dict[str, Any]] = {}
    for it in twse_items + tpex_items + us_items:
        all_items_by_symbol[it["symbol"]] = it
    items = list(all_items_by_symbol.values())

    if not items:
        sys.stderr.write("[ERROR] 全部來源都失敗，無資料可 upsert\n")
        raise SystemExit(2)

    logger.info(
        "seed_stock_list.merged total=%d twse=%d tpex=%d us=%d",
        len(items), len(twse_items), len(tpex_items), len(us_items),
    )

    written = await upsert_to_db(items)

    # 印 summary 給 CI 看
    sys.stdout.write(
        f"\n[OK] seed_stock_list done\n"
        f"  TWSE: {len(twse_items)}\n"
        f"  TPEX: {len(tpex_items)}\n"
        f"  US (hardcoded): {len(us_items)}\n"
        f"  Total upserted: {written}\n"
    )
    sys.stdout.flush()

    if written < 1500:
        sys.stderr.write(
            f"[WARN] 總筆數 {written} < 1500（健康檢查門檻），"
            "可能是 TWSE/TPEX OpenAPI 失敗。檢查網路 + 重跑\n"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

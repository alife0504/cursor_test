"""seed_demo_data.py — 為數檔知名台股填 demo 資料，讓資料頁在「有資料」狀態下可檢視。

填入（皆 dev/demo，強制 APP_ENV != prod）：
- stock_list（8 檔 TWSE，idempotent upsert）
- stock_prices：每檔近 15 交易日 OHLCV（source='dev-seed'）→ 市場總覽 movers/漲跌家數、選股 close、儀表板
- institutional_trading：最新交易日三大法人買賣超 → 三大法人頁
- news_metadata：每檔 3 則新聞（情緒輪替）→ 新聞情緒頁
- announcements：每檔 2 則公告 → 重大公告頁
- user_watchlist：為 admin 加 5 檔自選股 → 自選股頁 / 儀表板

清除：
    DELETE FROM stock_prices WHERE source='dev-seed';
    DELETE FROM institutional_trading WHERE source='dev-seed';
    DELETE FROM news_metadata WHERE extra_meta->>'seed'='dev';
    DELETE FROM announcements WHERE extra_meta->>'seed'='dev';

⚠️ demo 資料、非真實行情。正式環境請用 make backfill / 真實資料源。

用法：
    cd C:\\Projects\\TradingAgents
    uv run --project backend python data-pipeline/scripts/seed_demo_data.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
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

_SEED = "dev-seed"
_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "tradingagents-tw.demo-seed")

# symbol, 名稱, 產業, 起始價
_STOCKS: list[tuple[str, str, str, float]] = [
    ("2330", "台積電", "半導體", 1000.0),
    ("2317", "鴻海", "其他電子", 210.0),
    ("2454", "聯發科", "半導體", 1300.0),
    ("2412", "中華電", "通信網路", 125.0),
    ("2882", "國泰金", "金融保險", 65.0),
    ("1303", "南亞", "塑膠", 75.0),
    ("2603", "長榮", "航運", 230.0),
    ("2308", "台達電", "電子零組件", 410.0),
]

_NEWS_SOURCES = ["經濟日報", "工商時報", "鉅亨網", "MoneyDJ"]
_SENTIMENTS = ["positive", "neutral", "negative"]
_ANNOUNCE_TYPES = ["法說會", "股利分派", "重大訊息"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed demo 台股資料（dev/demo）")
    p.add_argument("--days", type=int, default=15, help="每檔回填交易日數（default 15）")
    p.add_argument("--yes", action="store_true", help="略過確認直接寫入")
    return p.parse_args()


def _trading_days(n: int) -> list:
    """回最舊→最新的 n 個交易日（粗略跳過週末）。"""
    out: list = []
    d = datetime.now(UTC).date()
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return list(reversed(out))


def _ohlcv_for(symbol: str, base: float, days: list) -> list[dict]:
    rng = random.Random(f"demo-{symbol}")  # noqa: S311 — demo 用
    rows: list[dict] = []
    price = base
    for d in days:
        drift = rng.uniform(-0.025, 0.027)
        open_p = price
        close_p = max(1.0, price * (1 + drift))
        high_p = max(open_p, close_p) * (1 + rng.uniform(0, 0.01))
        low_p = min(open_p, close_p) * (1 - rng.uniform(0, 0.01))
        vol = rng.randint(5_000, 60_000) * 1000
        rows.append(
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
    return rows


async def _seed(days: int) -> dict[str, int]:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.database import dispose_db_connections, get_rw_engine
    from app.models.news import Announcement, NewsMetadata
    from app.models.price import StockPrice
    from app.models.stock import StockList
    from app.models.tw_specific import InstitutionalTrading
    from app.models.user import User
    from app.models.watchlist import UserWatchlist

    counts = {"stocks": 0, "ohlcv": 0, "institutional": 0, "news": 0, "announce": 0, "watchlist": 0}
    trading = _trading_days(days)
    latest = trading[-1]
    now = datetime.now(UTC)

    engine = get_rw_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as s:
            for idx, (symbol, name, industry, base) in enumerate(_STOCKS):
                rng = random.Random(f"meta-{symbol}")  # noqa: S311

                # 1. stock_list
                await s.execute(
                    pg_insert(StockList)
                    .values(
                        symbol=symbol, market="TWSE", name=name,
                        short_name=name, industry=industry, is_active=True,
                    )
                    .on_conflict_do_update(
                        index_elements=["symbol"],
                        set_={"name": name, "industry": industry, "is_active": True},
                    )
                )
                counts["stocks"] += 1

                # 2. stock_prices
                for r in _ohlcv_for(symbol, base, trading):
                    await s.execute(
                        pg_insert(StockPrice)
                        .values(symbol=symbol, source=_SEED, **r)
                        .on_conflict_do_update(
                            index_elements=["symbol", "date"],
                            set_={
                                "open": r["open"], "high": r["high"], "low": r["low"],
                                "close": r["close"], "volume": r["volume"], "source": _SEED,
                            },
                        )
                    )
                    counts["ohlcv"] += 1

                # 3. 三大法人（最新交易日）
                fnet = rng.randint(-40_000_000, 50_000_000)
                tnet = rng.randint(-8_000_000, 12_000_000)
                dnet = rng.randint(-5_000_000, 5_000_000)
                await s.execute(
                    pg_insert(InstitutionalTrading)
                    .values(
                        symbol=symbol, date=latest,
                        foreign_buy=max(fnet, 0) + rng.randint(0, 20_000_000),
                        foreign_sell=max(-fnet, 0) + rng.randint(0, 20_000_000),
                        foreign_net=fnet,
                        trust_buy=max(tnet, 0) + rng.randint(0, 4_000_000),
                        trust_sell=max(-tnet, 0) + rng.randint(0, 4_000_000),
                        trust_net=tnet,
                        dealer_buy=max(dnet, 0) + rng.randint(0, 2_000_000),
                        dealer_sell=max(-dnet, 0) + rng.randint(0, 2_000_000),
                        dealer_net=dnet, source=_SEED,
                    )
                    .on_conflict_do_update(
                        index_elements=["symbol", "date"],
                        set_={"foreign_net": fnet, "trust_net": tnet, "dealer_net": dnet, "source": _SEED},
                    )
                )
                counts["institutional"] += 1

                # 4. 新聞（3 則，情緒輪替）
                for j in range(3):
                    sent = _SENTIMENTS[(idx + j) % 3]
                    nid = uuid.uuid5(_NS, f"news-{symbol}-{j}")
                    score = {"positive": "0.6", "neutral": "0.0", "negative": "-0.5"}[sent]
                    await s.execute(
                        pg_insert(NewsMetadata)
                        .values(
                            id=nid, symbol=symbol, market="TWSE",
                            title=f"{name}（{symbol}）{['法說會釋出展望','外資調升目標價','短線量能變化值得留意'][j]}",
                            summary=f"這是 {name} 的 demo 新聞摘要（{sent}）。",
                            source=_NEWS_SOURCES[(idx + j) % len(_NEWS_SOURCES)],
                            url="https://example.com/news",
                            published_at=now - timedelta(hours=3 * j + idx),
                            sentiment=sent, sentiment_score=Decimal(score),
                            extra_meta={"seed": "dev"},
                        )
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={"sentiment": sent, "title": f"{name}（{symbol}）demo 新聞 {j}"},
                        )
                    )
                    counts["news"] += 1

                # 5. 公告（2 則）
                for j in range(2):
                    aid = uuid.uuid5(_NS, f"ann-{symbol}-{j}")
                    atype = _ANNOUNCE_TYPES[(idx + j) % len(_ANNOUNCE_TYPES)]
                    await s.execute(
                        pg_insert(Announcement)
                        .values(
                            id=aid, symbol=symbol, market="TWSE",
                            announcement_type=atype,
                            title=f"{name} {atype}公告",
                            url="https://example.com/announcement",
                            published_at=now - timedelta(days=j, hours=idx),
                            extra_meta={"seed": "dev"},
                        )
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={"announcement_type": atype},
                        )
                    )
                    counts["announce"] += 1

            # 6. admin 自選股（前 5 檔）
            admin_email = getattr(settings, "ADMIN_EMAIL", None) or "admin@example.com"
            admin_id = (
                await s.execute(select(User.id).where(User.email == admin_email))
            ).scalar_one_or_none()
            if admin_id is not None:
                tags = ["核心持股", "核心持股", "觀察", "存股", "觀察"]
                for i, (symbol, *_rest) in enumerate(_STOCKS[:5]):
                    await s.execute(
                        pg_insert(UserWatchlist)
                        .values(
                            user_id=admin_id, symbol=symbol, market="TWSE",
                            tag=tags[i], sort_order=i,
                        )
                        .on_conflict_do_nothing(
                            constraint="uq_user_watchlist_user_symbol_market"
                        )
                    )
                    counts["watchlist"] += 1
            else:
                logger.warning("seed_demo.admin_not_found", email=admin_email)

            await s.commit()
    finally:
        await dispose_db_connections()
    return counts


def main() -> None:
    env = (settings.APP_ENV or "dev").lower()
    if env not in {"dev", "test"}:
        sys.stderr.write(f"[ERROR] 拒絕在 APP_ENV={env} 寫入 demo 資料（只允許 dev / test）。\n")
        raise SystemExit(2)

    args = parse_args()
    if not args.yes:
        sys.stdout.write(
            f"將為 {len(_STOCKS)} 檔台股寫入 demo 資料（OHLCV/三大法人/新聞/公告/自選股，"
            f"source=dev-seed，APP_ENV={env}）。\n這是 demo 資料，非真實行情。加 --yes 確認執行。\n"
        )
        return

    counts = asyncio.run(_seed(args.days))
    sys.stdout.write(f"[OK] seed_demo_data 完成：{counts}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

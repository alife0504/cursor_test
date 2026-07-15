"""Phase 10 — MarketService。

依 PLAN.md 第 17.5 章 cache + 第 10.5 章三大法人。

設計：
- 大盤 overview cache 5min（Key: cache:market:overview:{market}）
- cache 失敗不擋 request → 直接走 DB（log warn）
- 三大法人 / movers 不 cache（資料變動少且每次 query 便宜）
"""

from __future__ import annotations

import json
from datetime import date as date_type
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.repos.market_repo import MarketRepository

logger = get_logger(__name__)

OVERVIEW_CACHE_TTL = 300  # 5 minutes
MARKET_VALUES = {"TW", "US"}


def _validate_market(market: str) -> str:
    m = (market or "TW").upper()
    if m not in MARKET_VALUES:
        raise ValidationError(
            message_zh="market 必須是 TW 或 US",
            field="market",
            value=market,
        )
    return m


# 預設指數定義。symbol 對齊 stock_prices 內的指數 OHLCV（TAIEX / TPEX），
# 報價由 get_overview 從 stock_prices 動態填入（見 _build_indices）。
DEFAULT_INDICES: dict[str, list[dict[str, str]]] = {
    "TW": [
        {"name": "加權指數", "symbol": "TAIEX"},
        {"name": "櫃買指數", "symbol": "TPEX"},
    ],
    "US": [
        {"name": "S&P 500", "symbol": "^GSPC"},
        {"name": "Nasdaq", "symbol": "^IXIC"},
        {"name": "Dow Jones", "symbol": "^DJI"},
    ],
}


class MarketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MarketRepository(session)

    # ── overview ────────────────────────────────────────
    async def get_overview(self, market: str) -> dict[str, Any]:
        m = _validate_market(market)
        # 嘗試 cache
        cache_key = f"cache:market:overview:{m}"
        try:
            redis = await get_redis(RedisDB.CACHE)
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("market.overview.cache_read_failed", error=str(exc), market=m)

        # 走 DB
        indices = await self._build_indices(m)
        as_of = await self.repo.get_latest_trading_date(m)
        if as_of is None:
            # 沒任何個股 stock_prices — 家數回 0，但指數仍可能有資料
            payload: dict[str, Any] = {
                "market": m,
                "as_of": datetime.utcnow().date().isoformat(),
                "indices": indices,
                "advance_count": 0,
                "decline_count": 0,
                "unchanged_count": 0,
                "total_volume": 0,
            }
        else:
            agg = await self.repo.get_overview_aggregates(m, as_of)
            payload = {
                "market": m,
                "as_of": as_of.isoformat(),
                "indices": indices,
                "advance_count": int(agg.get("advance") or 0),
                "decline_count": int(agg.get("decline") or 0),
                "unchanged_count": int(agg.get("unchanged") or 0),
                "total_volume": int(agg.get("volume") or 0),
            }

        # 寫 cache（失敗不擋）
        try:
            redis = await get_redis(RedisDB.CACHE)
            await redis.set(cache_key, json.dumps(payload), ex=OVERVIEW_CACHE_TTL)
        except Exception as exc:
            logger.warning("market.overview.cache_write_failed", error=str(exc), market=m)

        return payload

    async def _build_indices(self, market: str) -> list[dict[str, Any]]:
        """組裝指數清單 + 從 stock_prices 填入最近報價（Decimal→str 以利 JSON cache）。"""
        defs = DEFAULT_INDICES.get(market, [])
        symbols = [d["symbol"] for d in defs]
        quotes = await self.repo.get_index_quotes(symbols) if symbols else {}

        def _s(v: Any) -> str | None:
            return str(v) if v is not None else None

        out: list[dict[str, Any]] = []
        for d in defs:
            q = quotes.get(d["symbol"], {})
            as_of = q.get("as_of")
            out.append(
                {
                    "name": d["name"],
                    "symbol": d["symbol"],
                    "close": _s(q.get("close")),
                    "change": _s(q.get("change")),
                    "change_pct": _s(q.get("change_pct")),
                    "volume": q.get("volume"),
                    "as_of": as_of.isoformat() if as_of else None,
                }
            )
        return out

    # ── institutional（TW only）─────────────────────────
    async def get_institutional(
        self, *, target_date: date_type | None = None, market: str = "TW", limit: int = 100
    ) -> tuple[date_type | None, list]:
        m = _validate_market(market)
        if m != "TW":
            raise ValidationError(
                message_zh="三大法人只支援台股（market=TW）",
                field="market",
                value=market,
            )
        if target_date is None:
            target_date = await self.repo.get_latest_trading_date("TW")
        if target_date is None:
            return None, []
        rows = await self.repo.get_institutional_for_date(target_date, market=m, limit=limit)
        return target_date, rows

    # ── movers ──────────────────────────────────────────
    async def get_movers(
        self,
        *,
        market: str = "TW",
        mover_type: str = "gainers",
        limit: int = 20,
    ) -> list:
        m = _validate_market(market)
        mt = (mover_type or "gainers").lower()
        if mt not in ("gainers", "losers", "volume"):
            raise ValidationError(
                message_zh="type 必須是 gainers / losers / volume",
                field="type",
                value=mover_type,
            )
        if limit < 1 or limit > 100:
            raise ValidationError(
                message_zh="limit 範圍 1~100",
                field="limit",
                value=limit,
            )
        return await self.repo.get_movers(m, mt, limit=limit)

    # ── calendar（mock，P17 完整）────────────────────────
    async def get_calendar(
        self,
        *,
        from_date: date_type,
        to_date: date_type,
        market: str | None = None,
    ) -> list[dict[str, Any]]:
        """Mock：回 from~to 之間的「月初」當作 mock event。

        P17 整合真實財報日曆後改寫。
        """
        if from_date > to_date:
            raise ValidationError(
                message_zh="from 不可晚於 to",
                field="date_range",
            )
        m = _validate_market(market or "TW")
        out: list[dict[str, Any]] = []
        cur = from_date
        while cur <= to_date:
            # 每月 1 日塞一個 mock 「公司財報週」
            if cur.day == 1:
                out.append(
                    {
                        "symbol": "MOCK",
                        "market": m,
                        "event_type": "earnings_week_start",
                        "event_date": cur.isoformat(),
                        "title": f"{m} 市場 — {cur.strftime('%Y-%m')} 財報季開跑",
                    }
                )
            cur = _next_day(cur)
        return out

    # ── 即時盤 snapshot（FinMind Sponsor 等級；未開通則優雅降級）──────────
    async def get_realtime_stock(self, symbols: list[str]) -> dict[str, Any]:
        """台股個股即時報價。回 {available, reason, message, as_of, quotes}。

        需 settings.FINMIND_REALTIME_ENABLED 且 token 為 Sponsor 等級；未達則回
        available=False + reason（tier_insufficient / quota_exceeded / disabled …）。
        """
        from app.core.config import settings
        from app.data_sources.tw.finmind_realtime import FinMindRealtimeClient

        client = FinMindRealtimeClient(settings)
        return await client.fetch_stock_snapshot(symbols)

    async def get_realtime_futures(self, contract_ids: list[str]) -> dict[str, Any]:
        """台指期 / 期貨即時報價。回 {available, reason, message, as_of, quotes}。"""
        from app.core.config import settings
        from app.data_sources.tw.finmind_realtime import FinMindRealtimeClient

        client = FinMindRealtimeClient(settings)
        return await client.fetch_futures_snapshot(contract_ids)


def _next_day(d: date_type) -> date_type:
    from datetime import timedelta

    return d + timedelta(days=1)


__all__ = ["MARKET_VALUES", "OVERVIEW_CACHE_TTL", "MarketService"]

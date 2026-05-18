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


# 預設 TW 三大主指數 / US 三大指數 — 真實 quote 暫無，先 placeholder
DEFAULT_INDICES: dict[str, list[dict[str, str]]] = {
    "TW": [
        {"name": "加權指數", "symbol": "^TWII"},
        {"name": "OTC 指數", "symbol": "^TWOII"},
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
        as_of = await self.repo.get_latest_trading_date(m)
        if as_of is None:
            # 沒任何 stock_prices — 回 placeholder
            payload: dict[str, Any] = {
                "market": m,
                "as_of": datetime.utcnow().date().isoformat(),
                "indices": DEFAULT_INDICES.get(m, []),
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
                "indices": DEFAULT_INDICES.get(m, []),
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


def _next_day(d: date_type) -> date_type:
    from datetime import timedelta

    return d + timedelta(days=1)


__all__ = ["MARKET_VALUES", "OVERVIEW_CACHE_TTL", "MarketService"]

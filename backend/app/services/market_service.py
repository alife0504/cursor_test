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

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.domain.disclosure_calendar import monthly_revenue_deadline, statement_deadline
from app.repos.market_repo import MarketRepository

logger = get_logger(__name__)

OVERVIEW_CACHE_TTL = 300  # 5 minutes
# 除權息事件變動極慢（公司決議後才變），快取久一點；法定期限則是純計算不用快取。
CALENDAR_CACHE_TTL = 3600  # 1 hour
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

    # ── calendar（真實：法定申報期限 + 除權息）──────────────
    async def get_calendar(
        self,
        *,
        from_date: date_type,
        to_date: date_type,
        market: str | None = None,
    ) -> list[dict[str, Any]]:
        """財報日曆（真實資料，非 mock）。目前提供兩類事件：

        1. **法定申報期限**（event_type='filing_deadline'）：依證交法 §36 推算，全市場共通，
           由法規決定故永遠正確、不需外部資料源。
        2. **除權息**（event_type='ex_dividend'）：來自 FinMind 本地庫的真實決議資料。

        刻意不提供「股東會 / 法說會」：FinMind 無此 dataset，與其顯示假資料不如不顯示。
        """
        if from_date > to_date:
            raise ValidationError(
                message_zh="from 不可晚於 to",
                field="date_range",
            )
        m = _validate_market(market or "TW")
        if m != "TW":
            # 目前僅台股有法定期限/除權息來源；美股待接
            return []

        events: list[dict[str, Any]] = _tw_filing_deadlines(from_date, to_date)
        events.extend(await self._tw_ex_dividend_events(from_date, to_date))
        events.sort(key=lambda e: (e["event_date"], e.get("symbol") or ""))
        return events

    async def _tw_ex_dividend_events(
        self, from_date: date_type, to_date: date_type
    ) -> list[dict[str, Any]]:
        """從 FinMind 本地庫讀除權息事件；未啟用或失敗時回空（日曆仍有法定期限可看）。"""
        if not getattr(settings, "FINMIND_LOCAL_ENABLED", False):
            return []

        cache_key = f"cache:market:calendar:exdiv:{from_date}:{to_date}"
        try:
            redis = await get_redis(RedisDB.CACHE)
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("market.calendar.cache_read_failed", error=str(exc))
            redis = None

        try:
            from app.data_sources.tw.finmind_local_source import FinMindLocalSource

            rows = await FinMindLocalSource(settings).fetch_dividend_events(from_date, to_date)
        except Exception as exc:
            # 日曆不該因為本地庫連不上就整頁掛掉
            logger.warning("market.calendar.exdiv_failed", error=str(exc))
            return []

        names = await self.repo.get_names_for([r["stock_id"] for r in rows])
        out: list[dict[str, Any]] = []
        for r in rows:
            sym = r["stock_id"]
            name = names.get(sym) or sym
            if r["kind"] == "cash":
                amount = r.get("cash")
                title = f"{name} 除息" + (f" {amount} 元" if amount else "")
            else:
                amount = r.get("stock_div")
                title = f"{name} 除權" + (f" {amount} 元" if amount else "")
            out.append(
                {
                    "symbol": sym,
                    "name": name,
                    "market": "TW",
                    "event_type": "ex_dividend",
                    "event_date": r["ex_date"].isoformat(),
                    "title": title,
                    "source": "finmind_local",
                }
            )

        if redis is not None:
            try:
                await redis.set(cache_key, json.dumps(out), ex=CALENDAR_CACHE_TTL)
            except Exception as exc:
                logger.warning("market.calendar.cache_write_failed", error=str(exc))
        return out


def _deadline_event(d: date_type, title: str) -> dict[str, Any]:
    """法定申報期限事件（全市場共通，故無個股 symbol）。"""
    return {
        "symbol": None,
        "name": None,
        "market": "TW",
        "event_type": "filing_deadline",
        "event_date": d.isoformat(),
        "title": title,
        "source": "statutory",
    }


def _tw_filing_deadlines(from_date: date_type, to_date: date_type) -> list[dict[str, Any]]:
    """產生 from~to 之間的法定申報期限事件。

    期限一律委派給 app.domain.disclosure_calendar（證交法 §36 的權威實作，已處理年報 vs
    季報、金融保險業例外、週末順延等）——不要在這裡重寫一份，那份才是單一事實來源。
    此處用 FilerCategory 預設值（一般公司），因日曆是全市場視角、不分個股類別。
    """
    out: list[dict[str, Any]] = []
    # 前後各多掃一年：年報期限落在次年（fiscal_year=Y 的年報在 Y+1/3/31），
    # 12 月營收期限也落在次年 1 月，不多掃會漏掉跨年的事件。
    for year in range(from_date.year - 1, to_date.year + 2):
        for quarter, label in (
            (1, f"{year} 第一季財報申報截止"),
            (2, f"{year} 半年度財報申報截止"),
            (3, f"{year} 第三季財報申報截止"),
            (4, f"{year} 年度財報申報截止"),
        ):
            out.append((statement_deadline(year, quarter), label))
        for month in range(1, 13):
            out.append(
                (
                    monthly_revenue_deadline(year, month),
                    f"{year}-{month:02d} 月營收公告截止",
                )
            )

    return [_deadline_event(d, t) for d, t in out if from_date <= d <= to_date]


def _next_day(d: date_type) -> date_type:
    from datetime import timedelta

    return d + timedelta(days=1)


__all__ = ["CALENDAR_CACHE_TTL", "MARKET_VALUES", "OVERVIEW_CACHE_TTL", "MarketService"]

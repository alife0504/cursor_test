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
# 盤中即時走勢快取（前端每 5 秒輪詢）：加權 5 秒序列輕故 5s＝真 5 秒即時；
# 台指全逐筆重（~2.5s）故 10s，仍即時但不過度重抓上游。
INTRADAY_CACHE_TTL_TAIEX = 5
INTRADAY_CACHE_TTL_TXF = 10
MARKET_VALUES = {"TW", "US"}


def _downsample(series: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    """把序列降採樣到 ~target 點：分桶、每桶取最後一筆（保留收盤感）。"""
    n = len(series)
    if n <= target or target <= 0:
        return series
    bucket = (n + target - 1) // target
    out: list[dict[str, Any]] = []
    for i in range(0, n, bucket):
        out.append(series[min(i + bucket - 1, n - 1)])
    return out


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
                "limit_up_count": 0,
                "limit_down_count": 0,
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
                "limit_up_count": int(agg.get("limit_up") or 0),
                "limit_down_count": int(agg.get("limit_down") or 0),
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
        self,
        *,
        target_date: date_type | None = None,
        market: str = "TW",
        limit: int = 100,
        order: str = "buy",
        by: str = "foreign",
    ) -> tuple[date_type | None, list, dict[str, int] | None]:
        """回 (日期, top-N rows, 全市場淨額合計)。

        rows 依某法人買賣超截斷（by=foreign/trust/dealer；order="buy" 買超最大 /
        "sell" 賣超最大）供表格/Top 榜；totals 由後端對全母體 SUM（與 order/by 無關），
        頁面 KPI 合計卡必須用 totals，不可拿截斷後的 rows 子集加總（方向會相反）。
        """
        m = _validate_market(market)
        if m != "TW":
            raise ValidationError(
                message_zh="三大法人只支援台股（market=TW）",
                field="market",
                value=market,
            )
        if target_date is None:
            # 用「最新法人資料日」而非最新股價日：法人盤後才出，且本地庫覆蓋日期常不同，
            # 用股價日（可能是今天、法人還沒出）會查到空 → 頁面誤顯示「無資料」。
            target_date = await self.repo.get_latest_institutional_date("TW")
        if target_date is None:
            return None, [], None
        ord_ = "sell" if str(order).lower() == "sell" else "buy"
        by_ = by if by in ("foreign", "trust", "dealer") else "foreign"
        rows = await self.repo.get_institutional_for_date(
            target_date, market=m, limit=limit, order=ord_, by=by_
        )
        totals = await self.repo.get_institutional_totals(target_date, market=m)
        return target_date, rows, totals

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

    # ── 即時大盤 / 漲跌榜（盤中；由 FinMind 全市場快照計算，僅 TW）──────────
    async def _active_realtime_stock_quotes(self) -> tuple[list[dict[str, Any]], str | None] | None:
        """取得「is_active 台股」的即時報價 list + as_of；即時不可用時回 None。

        全市場快照含 ETF/指數/權證，這裡只留 stock_list 的 active 台股（與盤後家數口徑一致），
        且過濾掉沒有漲跌幅的（未成交）。
        """
        from app.core.config import settings
        from app.data_sources.tw.finmind_realtime import FinMindRealtimeClient

        snap = await FinMindRealtimeClient(settings).fetch_all_stock_quotes()
        if not snap.get("available"):
            return None
        active = await self.repo.get_active_symbols("TW")
        quotes = [
            q
            for q in snap.get("quotes", [])
            if q.get("symbol") in active and q.get("change_rate") is not None
        ]
        return quotes, snap.get("as_of")

    async def get_realtime_overview(self) -> dict[str, Any] | None:
        """即時大盤：由快照算漲跌家數 + 總量。即時不可用時回 None（caller 退回盤後）。"""
        got = await self._active_realtime_stock_quotes()
        if got is None:
            return None
        quotes, as_of = got
        adv = dec = unc = lu = ld = 0
        vol = 0
        for q in quotes:
            cr = q["change_rate"]
            if cr > 0:
                adv += 1
            elif cr < 0:
                dec += 1
            else:
                unc += 1
            # 漲停/跌停：漲跌幅 ±9.9%～±10.5%（台股 ±10%，tick 取整實際約 9.7～10%；
            # 上界排除除權息參考價調整等異常）。與 get_overview_aggregates 同一判定。
            if 9.9 <= cr <= 10.5:
                lu += 1
            elif -10.5 <= cr <= -9.9:
                ld += 1
            vol += int(q.get("total_volume") or 0)
        return {
            "advance_count": adv,
            "decline_count": dec,
            "unchanged_count": unc,
            "limit_up_count": lu,
            "limit_down_count": ld,
            "total_volume": vol,
            "as_of": as_of,
            "realtime": True,
        }

    async def get_heatmap(
        self, *, top_per_industry: int = 18, max_industries: int = 28
    ) -> dict[str, Any]:
        """板塊熱力圖：產業分組、格子=個股。每檔同時回 chg(即時漲跌%) 與 flow(資金流億)，
        大小用成交值；前端切換配色/標籤免重抓、格子不會跳。

        chg 來源：盤中用 FinMind 即時快照、收盤後退回 EOD(對前一交易日)。
        flow 來源：三大法人當日淨買賣超金額(億)＝淨股數×最新收盤（盤後才有、日內不變）。
        """
        industry_map = await self.repo.get_industry_map("TW")  # {sym: {industry, name}}
        realtime = False
        as_of = None

        got = await self._active_realtime_stock_quotes()
        if got is not None:
            quotes, as_of = got
            realtime = True
            base = [
                {
                    "symbol": q["symbol"],
                    "chg": round(float(q["change_rate"]), 2),
                    "value": float(q.get("total_amount") or q.get("amount") or 0),
                }
                for q in quotes
            ]
        else:
            base = [
                {"symbol": r["symbol"], "chg": r["metric"], "value": r["value"]}
                for r in await self.repo.get_eod_change_rows("TW")
            ]

        flow_map = {r["symbol"]: r["metric"] for r in await self.repo.get_flow_rows("TW")}

        groups: dict[str, dict[str, Any]] = {}
        for r in base:
            info = industry_map.get(r["symbol"])
            if not info:
                continue
            g = groups.setdefault(
                info["industry"],
                {"name": info["industry"], "value": 0.0, "flow_total": 0.0, "stocks": []},
            )
            flow = flow_map.get(r["symbol"], 0.0)
            g["stocks"].append(
                {
                    "symbol": r["symbol"],
                    "name": info["name"],
                    "chg": r["chg"],
                    "flow": flow,
                    "value": r["value"],
                }
            )
            g["value"] += r["value"]
            g["flow_total"] += flow

        industries = []
        for g in groups.values():
            g["stocks"].sort(key=lambda s: s["value"], reverse=True)
            g["stocks"] = g["stocks"][:top_per_industry]
            industries.append(g)
        industries.sort(key=lambda x: x["value"], reverse=True)
        industries = industries[:max_industries]

        return {
            "realtime": realtime,
            "as_of": as_of,
            "industries": [
                {
                    "name": g["name"],
                    "value": round(g["value"], 0),
                    "flow_total": round(g["flow_total"], 2),
                    "stocks": g["stocks"],
                }
                for g in industries
            ],
        }

    async def get_realtime_movers(self, *, mover_type: str = "gainers", limit: int = 10) -> Any:
        """即時漲跌 / 成交量榜；即時不可用時回 None（caller 退回盤後）。"""
        mt = (mover_type or "gainers").lower()
        if mt not in ("gainers", "losers", "volume"):
            raise ValidationError(message_zh="type 必須是 gainers / losers / volume", field="type")
        limit = max(1, min(limit, 100))
        got = await self._active_realtime_stock_quotes()
        if got is None:
            return None
        quotes, _ = got

        if mt == "volume":
            ranked = sorted(quotes, key=lambda q: q.get("total_volume") or 0, reverse=True)
        else:
            ranked = sorted(quotes, key=lambda q: q["change_rate"], reverse=(mt == "gainers"))
        top = ranked[:limit]
        names = await self.repo.get_names_for([q["symbol"] for q in top])
        return [
            {
                "symbol": q["symbol"],
                "name": names.get(q["symbol"]),
                "close": str(q["price"]) if q.get("price") is not None else None,
                "change_pct": str(q["change_rate"]),
                "volume": int(q.get("total_volume") or 0),
            }
            for q in top
        ]

    async def get_intraday(self, symbol: str) -> dict[str, Any]:
        """盤中即時走勢序列 + 關鍵水位（平盤/漲停/跌停/最高/最低/當下）。

        symbol＝"TAIEX"（加權指數，FinMind 5 秒序列，Free）或 "TXF"（台指全，逐筆降採樣，Sponsor）。
        走勢線用當日盤中序列；水位取自即時 snapshot（當下/漲跌/最高/最低），平盤＝當下−漲跌，
        漲停/跌停＝平盤×1.1／0.9（指數無實體漲跌停，故 has_limit=False，前端僅作參考線）。
        """
        sym = (symbol or "TAIEX").upper()
        if sym not in ("TAIEX", "TXF"):
            raise ValidationError(message_zh="symbol 必須是 TAIEX 或 TXF", field="symbol", value=symbol)

        cache_key = f"cache:market:intraday:{sym}"
        try:
            redis = await get_redis(RedisDB.CACHE)
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("market.intraday.cache_read_failed", error=str(exc))

        from app.data_sources.tw.finmind_realtime import FinMindRealtimeClient
        from app.data_sources.tw.finmind_source import FinMindSource

        rt = FinMindRealtimeClient(settings)
        # 交易日一律取自「指數快照」的日盤時間，避免用期貨夜盤 as_of（跨午夜）抓到隔日空資料。
        idx_snap = await rt.fetch_index_snapshot()
        idx_quotes = idx_snap.get("quotes") or []
        as_of = idx_snap.get("as_of")
        trade_date: date_type | None = None
        if as_of:
            try:
                trade_date = date_type.fromisoformat(str(as_of)[:10])
            except ValueError:
                trade_date = None
        if trade_date is None:
            trade_date = await self.repo.get_latest_trading_date("TW")

        if sym == "TAIEX":
            quote = next((q for q in idx_quotes if q.get("symbol") == "TAIEX"), None)
        else:
            fut_snap = await rt.fetch_futures_snapshot(["TXF"])
            fq = fut_snap.get("quotes") or []
            quote = fq[0] if fq else None

        series: list[dict[str, Any]] = []
        if trade_date is not None:
            src = FinMindSource(settings)
            try:
                series = (
                    await src.fetch_index_intraday(trade_date)
                    if sym == "TAIEX"
                    else await src.fetch_futures_intraday(trade_date)
                )
            except Exception as exc:
                logger.warning("market.intraday.series_failed", symbol=sym, error=str(exc))
        series = _downsample(series, 240)

        def _f(v: Any) -> float | None:
            try:
                return float(v) if v is not None and v != "" else None
            except (TypeError, ValueError):
                return None

        snap_price = _f(quote.get("price")) if quote else None
        snap_chg = _f(quote.get("change")) if quote else None
        # 平盤＝snapshot 當下−漲跌（該盤前收／前結算）
        prev_close = (
            round(snap_price - snap_chg, 2)
            if (snap_price is not None and snap_chg is not None)
            else None
        )
        prices = [p["price"] for p in series]
        if prices:
            # 當下／最高／最低都取自走勢線本身 → 標記與線一致（台指全 snapshot 可能是夜盤，不一致）
            cur = prices[-1]
            hi = max(prices)
            lo = min(prices)
        else:
            cur = snap_price
            hi = _f(quote.get("high")) if quote else None
            lo = _f(quote.get("low")) if quote else None
        if cur is not None and prev_close:
            chg = round(cur - prev_close, 2)
            chg_rate = round(chg / prev_close * 100, 2)
        else:
            chg = snap_chg
            chg_rate = _f(quote.get("change_rate")) if quote else None
        limit_up = round(prev_close * 1.1, 2) if prev_close is not None else None
        limit_down = round(prev_close * 0.9, 2) if prev_close is not None else None

        payload: dict[str, Any] = {
            "symbol": sym,
            "as_of": as_of,
            "series": series,
            "current": cur,
            "change": chg,
            "change_rate": chg_rate,
            "prev_close": prev_close,
            "high": hi,
            "low": lo,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "has_limit": sym == "TXF",
        }
        try:
            redis = await get_redis(RedisDB.CACHE)
            # 差異化快取：加權 5 秒序列輕（~0.9s）→ 5s 對齊前端輪詢＝真 5 秒即時；
            # 台指全逐筆重（10 萬筆 ~2.5s）→ 10s，仍即時但不過度重抓上游。
            ttl = INTRADAY_CACHE_TTL_TAIEX if sym == "TAIEX" else INTRADAY_CACHE_TTL_TXF
            await redis.set(cache_key, json.dumps(payload), ex=ttl)
        except Exception as exc:
            logger.warning("market.intraday.cache_write_failed", error=str(exc))
        return payload

    # ── calendar（真實：法定申報期限 + 除權息）──────────────
    async def get_calendar(
        self,
        *,
        from_date: date_type,
        to_date: date_type,
        market: str | None = None,
    ) -> list[dict[str, Any]]:
        """財報日曆（真實資料，非 mock）。提供的事件：

        1. **法定申報期限**（event_type='filing_deadline'）：依證交法 §36 推算（含月營收/季報截止）。
        2. **除權息**（event_type='ex_dividend'）：來自 FinMind 本地庫的真實決議資料。
        3. **美國重大數據**（event_type='us_econ'）：FOMC/非農/ISM 等能精確定日的排程（台北時間）。

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

        from app.domain.us_econ_calendar import us_econ_events

        events: list[dict[str, Any]] = _tw_filing_deadlines(from_date, to_date)
        events.extend(await self._tw_ex_dividend_events(from_date, to_date))
        events.extend(us_econ_events(from_date, to_date))
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

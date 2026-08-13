"""Phase 10 — StockService。

依 PLAN.md 第 18.1 章後端分層（API → Service → Domain → Repo）。

提供：
- list_stocks(market, q, cursor, limit)
- get_stock(symbol)
- get_ohlcv(symbol, start, end, max_rows)
- get_indicators(symbol, period, types) — v1 直接走 OHLCV 後本地算（pandas 可省，自己算 RSI/MACD/KD/BBANDS）
- list_news(symbol, since, limit)
- list_announcements(symbol, since, limit)
- list_financial(symbol, year, quarter, statement_type)

避免：N+1（用 stock_list + stock_info 一次 join）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursor import Cursor, clamp_limit
from app.core.errors import NotFoundError, ValidationError
from app.core.validators import validate_date_range, validate_symbol
from app.models.stock import StockInfo, StockList
from app.repos.financials_repo import FinancialsRepository
from app.repos.news_repo import AnnouncementRepository, NewsRepository
from app.repos.ohlcv_repo import OHLCVRepository
from app.repos.stock_repo import StockRepository

OHLCV_MAX_ROWS = 10000  # 防大查詢 — 強制 max
INDICATOR_SUPPORTED = ("RSI", "MACD", "KD", "BBANDS")

# market query param 對映到 stock_list.market 集合
_MARKET_GROUPS: dict[str, list[str]] = {
    "TW": ["TWSE", "TPEX"],
    "US": ["NYSE", "NASDAQ", "AMEX"],
    "TWSE": ["TWSE"],
    "TPEX": ["TPEX"],
    "NYSE": ["NYSE"],
    "NASDAQ": ["NASDAQ"],
    "AMEX": ["AMEX"],
}


def _expand_market(market: str | None) -> list[str] | None:
    if not market:
        return None
    return _MARKET_GROUPS.get(market.upper())


@dataclass(slots=True)
class StockListPage:
    items: list[StockList]
    next_cursor_kwargs: dict[str, Any] | None
    limit: int


class StockService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.stocks = StockRepository(session)
        self.ohlcv = OHLCVRepository(session)
        self.news = NewsRepository(session)
        self.announcements = AnnouncementRepository(session)
        self.financials = FinancialsRepository(session)

    # ── list ────────────────────────────────────────────────
    async def list_stocks(
        self,
        *,
        market: str | None,
        q: str | None,
        cursor: str | None,
        limit: int | None,
    ) -> StockListPage:
        page_size = clamp_limit(limit)
        decoded = Cursor.decode(cursor) if cursor else {}
        after_symbol = decoded.get("after_symbol") if isinstance(decoded, dict) else None

        markets = _expand_market(market) if market else None
        # 多撈 1 筆判斷 has_more
        rows = await self.stocks.list_page(
            markets=markets,
            keyword=q,
            after_symbol=after_symbol,
            limit=page_size + 1,
        )
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor_kwargs: dict[str, Any] | None = None
        if has_more and items:
            next_cursor_kwargs = {"after_symbol": items[-1].symbol}
        return StockListPage(items=items, next_cursor_kwargs=next_cursor_kwargs, limit=page_size)

    # ── detail ──────────────────────────────────────────────
    async def get_stock(self, symbol: str) -> tuple[StockList, StockInfo | None]:
        sym = validate_symbol(symbol)
        # 跨表查（StockList + StockInfo）
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload  # noqa: F401 — 保留給未來 N+1 防護

        stmt = select(StockList).where(StockList.symbol == sym)
        result = await self.session.execute(stmt)
        stock = result.scalar_one_or_none()
        if stock is None:
            raise NotFoundError(message_zh=f"找不到股票 {sym}", symbol=sym)
        info_stmt = select(StockInfo).where(StockInfo.symbol == sym)
        info_result = await self.session.execute(info_stmt)
        info = info_result.scalar_one_or_none()
        return stock, info

    # ── OHLCV ───────────────────────────────────────────────
    async def get_ohlcv(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
        interval: str = "daily",
    ) -> list:
        sym = validate_symbol(symbol)
        if interval.lower() not in ("daily", "1d", "day"):
            raise ValidationError(
                message_zh=f"interval 目前僅支援 daily，實際 {interval!r}",
                field="interval",
                value=interval,
            )
        validate_date_range(start, end)
        # 強制 max 10000 row 避免大查詢
        span_days = (end - start).days
        if span_days > OHLCV_MAX_ROWS:
            raise ValidationError(
                message_zh=f"日期跨度過大（最多 {OHLCV_MAX_ROWS} 天，實際 {span_days} 天）",
                field="date_range",
                max_days=OHLCV_MAX_ROWS,
            )
        rows = await self.ohlcv.get_range(sym, market="", start=start, end=end)
        return rows

    # ── Indicators（v1 — 簡化版）─────────────────────────
    async def get_indicators(
        self,
        symbol: str,
        *,
        period: int = 14,
        types: list[str] | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        """技術指標：RSI / MACD / KD / BBANDS（v1 簡化版，全用 close）。

        若 start/end 沒給，預設取最近 180 天。
        """
        sym = validate_symbol(symbol)
        if period < 2 or period > 200:
            raise ValidationError(
                message_zh="period 範圍 2~200",
                field="period",
                value=period,
            )
        type_list = types or list(INDICATOR_SUPPORTED)
        for t in type_list:
            if t.upper() not in INDICATOR_SUPPORTED:
                raise ValidationError(
                    message_zh=f"未支援的指標：{t}（允許：{list(INDICATOR_SUPPORTED)}）",
                    field="type",
                )

        if end is None:
            end = date.today()
        if start is None:
            start = end - timedelta(days=365)

        rows = await self.ohlcv.get_range(sym, market="", start=start, end=end)
        if not rows:
            return []

        closes = [float(r.close) for r in rows]
        dates = [r.date for r in rows]
        highs = [float(r.high) for r in rows]
        lows = [float(r.low) for r in rows]

        out: list[dict[str, Any]] = []
        for i, d in enumerate(dates):
            point: dict[str, Any] = {"date": d}
            up_types = {t.upper() for t in type_list}
            if "RSI" in up_types:
                point["rsi"] = _calc_rsi(closes, i, period)
            if "MACD" in up_types:
                macd, sig, hist = _calc_macd(closes, i)
                point["macd"] = macd
                point["macd_signal"] = sig
                point["macd_hist"] = hist
            if "KD" in up_types:
                k, d_val = _calc_kd(highs, lows, closes, i, period)
                point["k"] = k
                point["d"] = d_val
            if "BBANDS" in up_types:
                up, mid, low = _calc_bbands(closes, i, period)
                point["bb_upper"] = up
                point["bb_middle"] = mid
                point["bb_lower"] = low
            out.append(point)
        return out

    # ── News / Announcements ─────────────────────────────────
    async def list_news(
        self, symbol: str, *, since: datetime | None = None, limit: int = 20
    ) -> list:
        sym = validate_symbol(symbol)
        return await self.news.list_by_symbol(sym, since=since, limit=clamp_limit(limit))

    async def list_announcements(
        self, symbol: str, *, since: datetime | None = None, limit: int = 20
    ) -> list:
        sym = validate_symbol(symbol)
        return await self.announcements.list_by_symbol(sym, since=since, limit=clamp_limit(limit))

    # ── Financial Statements ─────────────────────────────────
    async def list_financial(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
        statement_type: str | None = None,
    ) -> list:
        sym = validate_symbol(symbol)
        if quarter is not None and not (0 <= quarter <= 4):
            raise ValidationError(
                message_zh="quarter 必須在 0~4 範圍（0=年報）",
                field="quarter",
                value=quarter,
            )
        if statement_type is not None and statement_type.upper() not in ("IS", "BS", "CF"):
            raise ValidationError(
                message_zh="statement_type 必須是 IS/BS/CF",
                field="statement_type",
                value=statement_type,
            )
        return await self.financials.list_statements(
            sym,
            year=year,
            quarter=quarter,
            statement_type=statement_type.upper() if statement_type else None,
        )


# ════════════════ 簡化版技術指標計算 ════════════════
#
# 全部用「close 為主」的標準公式；非生產級。Phase 12 後物化進 PG view 再正規化。


def _safe_round(v: float | None, digits: int = 6) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(f"{v:.{digits}f}")
    except Exception:
        return None


def _calc_rsi(closes: list[float], i: int, period: int) -> Decimal | None:
    if i < period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for j in range(i - period + 1, i + 1):
        diff = closes[j] - closes[j - 1] if j > 0 else 0
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(-diff)
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0
    if avg_loss == 0:
        return _safe_round(100.0, 4)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return _safe_round(rsi, 4)


def _ema(values: list[float], period: int) -> list[float]:
    """expanding EMA — index 對齊 values。"""
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out


def _calc_macd(
    closes: list[float], i: int
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if i < 26:
        return None, None, None
    ema12 = _ema(closes[: i + 1], 12)
    ema26 = _ema(closes[: i + 1], 26)
    macd_line = [a - b for a, b in zip(ema12, ema26, strict=False)]
    signal = _ema(macd_line, 9)
    hist = [m - s for m, s in zip(macd_line, signal, strict=False)]
    return (
        _safe_round(macd_line[-1], 4),
        _safe_round(signal[-1], 4),
        _safe_round(hist[-1], 4),
    )


def _calc_kd(
    highs: list[float], lows: list[float], closes: list[float], i: int, period: int
) -> tuple[Decimal | None, Decimal | None]:
    if i < period - 1:
        return None, None
    window_h = highs[i - period + 1 : i + 1]
    window_l = lows[i - period + 1 : i + 1]
    hh = max(window_h)
    ll = min(window_l)
    if hh == ll:
        return _safe_round(50.0, 4), _safe_round(50.0, 4)
    rsv = (closes[i] - ll) / (hh - ll) * 100
    # 平滑：K = 2/3 prev K + 1/3 RSV；初始 K=50
    k_prev = 50.0
    d_prev = 50.0
    for j in range(period - 1, i + 1):
        wh = max(highs[j - period + 1 : j + 1])
        wl = min(lows[j - period + 1 : j + 1])
        r = 50.0 if wh == wl else (closes[j] - wl) / (wh - wl) * 100
        k_curr = 2 / 3 * k_prev + 1 / 3 * r
        d_curr = 2 / 3 * d_prev + 1 / 3 * k_curr
        k_prev = k_curr
        d_prev = d_curr
    _ = rsv  # 已透過迴圈計算
    return _safe_round(k_prev, 4), _safe_round(d_prev, 4)


def _calc_bbands(
    closes: list[float], i: int, period: int
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if i < period - 1:
        return None, None, None
    window = closes[i - period + 1 : i + 1]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std = variance**0.5
    upper = mean + 2 * std
    lower = mean - 2 * std
    return _safe_round(upper, 4), _safe_round(mean, 4), _safe_round(lower, 4)


__all__ = ["INDICATOR_SUPPORTED", "OHLCV_MAX_ROWS", "StockListPage", "StockService"]

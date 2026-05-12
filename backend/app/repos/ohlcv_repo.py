"""OHLCVRepository — stock_prices (TimescaleDB hypertable) CRUD。

依 PLAN.md 第 10.4 章 + 第 20.2 章 + 第 14.10 章 retention。

提供：
- get_range(symbol, market, start, end)
- upsert_many(df): bulk upsert（PG INSERT ... ON CONFLICT DO UPDATE）
- latest_date(symbol, market): 最後一筆 date
- gaps(symbol, start, end, trading_days): 缺資料的日期（只含交易日）
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging_config import get_logger
from app.models.price import StockPrice
from app.repos.base import BaseRepository

logger = get_logger(__name__)


class OHLCVRepository(BaseRepository):
    async def get_range(self, symbol: str, market: str, start: date, end: date) -> list[StockPrice]:
        # market 不在 stock_prices PK，但 stock_list FK 已連動 → 用 symbol 即可
        # 若需 market 過濾，從 stock_list JOIN 取（這裡簡化只用 symbol + date）
        stmt = (
            select(StockPrice)
            .where(
                and_(
                    StockPrice.symbol == symbol,
                    StockPrice.date >= start,
                    StockPrice.date <= end,
                )
            )
            .order_by(StockPrice.date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def latest_date(self, symbol: str, market: str) -> date | None:
        stmt = select(func.max(StockPrice.date)).where(StockPrice.symbol == symbol)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def gaps(
        self,
        symbol: str,
        market: str,
        start: date,
        end: date,
        *,
        weekday_only: bool = True,
    ) -> list[date]:
        """回傳區間內缺資料的日期。

        Args:
            weekday_only: True → 只回工作日（Mon-Fri，不考慮國定假日；
              P7 整合 trading_calendar 後再精準化）。
        """
        existing = {p.date for p in await self.get_range(symbol, market, start, end)}
        out: list[date] = []
        cur = start
        while cur <= end:
            if weekday_only and cur.weekday() >= 5:
                cur += timedelta(days=1)
                continue
            if cur not in existing:
                out.append(cur)
            cur += timedelta(days=1)
        return out

    async def upsert_many(
        self,
        rows: list[dict[str, Any]],
        *,
        source: str | None = None,
        commit: bool = False,
    ) -> int:
        """INSERT ... ON CONFLICT (symbol, date) DO UPDATE — bulk upsert。

        Args:
            rows: list[dict]，每筆必須含 symbol / date / open / high / low / close;
                volume 可選（預設 0）；turnover/source 可選。
            source: 若 row 沒帶 source，給統一值。
            commit: 是否在 repo 內 commit。

        Returns:
            已執行筆數。
        """
        if not rows:
            return 0
        # 清理：丟掉 None / NaN 的關鍵欄位
        clean: list[dict[str, Any]] = []
        for r in rows:
            if not r.get("symbol") or r.get("date") is None:
                continue
            # 必填 OHLC
            if any(r.get(c) is None for c in ("open", "high", "low", "close")):
                continue
            entry = {
                "symbol": r["symbol"],
                "date": r["date"],
                "open": _ensure_decimal(r["open"]),
                "high": _ensure_decimal(r["high"]),
                "low": _ensure_decimal(r["low"]),
                "close": _ensure_decimal(r["close"]),
                "adjusted_close": _ensure_decimal(r.get("adjusted_close")),
                "volume": int(r.get("volume") or 0),
                "turnover": _ensure_decimal(r.get("turnover")),
                "source": r.get("source") or source,
            }
            clean.append(entry)
        if not clean:
            return 0

        stmt = pg_insert(StockPrice).values(clean)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "adjusted_close": stmt.excluded.adjusted_close,
                "volume": stmt.excluded.volume,
                "turnover": stmt.excluded.turnover,
                "source": stmt.excluded.source,
            },
        )
        await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return len(clean)


def _ensure_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, int | float):
        if isinstance(v, float) and v != v:  # NaN check
            return None
        return Decimal(str(v))
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s:
            return None
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


__all__ = ["OHLCVRepository"]

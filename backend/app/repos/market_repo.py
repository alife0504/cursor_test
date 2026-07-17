"""Phase 10 — MarketRepository。

依 PLAN.md 第 10.5 章三大法人 / 第 17.5 章 cache。

提供：
- get_overview_aggregates(market, as_of)：以 stock_prices + stock_list 聚合「漲跌家數 / 總成交量」
- get_institutional_for_date(date, market)：列出三大法人某日紀錄
- get_movers(market, type, limit)：漲幅 / 跌幅 / 成交量排行
- get_latest_trading_date(market)：找最近一個 stock_prices 有資料的日期

注意：本層只負責 SQL；cache 由 service 層處理（依 17.5 章規範）。
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    Numeric,
    Result,
    String,
    and_,
    case,
    cast,
    func,
    literal,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.price import StockPrice
from app.models.stock import StockList
from app.models.tw_specific import InstitutionalTrading, MarginTrading
from app.repos.base import BaseRepository

# 多列 upsert 每塊列數 —— asyncpg 單語句參數上限 32767；margin 11 欄/列、
# institutional 12 欄/列，取 1,000 列/塊（≤12,000 參數）遠低於上限。
_UPSERT_CHUNK = 1000

# 把使用者輸入的 market code 映射到 stock_list.market 集合
_MARKET_GROUPS: dict[str, tuple[str, ...]] = {
    "TW": ("TWSE", "TPEX"),
    "US": ("NYSE", "NASDAQ", "AMEX"),
}


def _market_filter(market: str) -> tuple[str, ...]:
    """回傳 stock_list.market 應該 in 的 enum 值。"""
    return _MARKET_GROUPS.get(market.upper(), (market.upper(),))


class MarketRepository(BaseRepository):
    """市場聚合查詢。"""

    # ── 最近一個交易日 ──────────────────────────────────────
    async def get_latest_trading_date(self, market: str) -> date_type | None:
        """找 stock_prices 中最近一筆 date（依 market 過濾）。"""
        markets = _market_filter(market)
        stmt = (
            select(func.max(StockPrice.date))
            .join(StockList, StockList.symbol == StockPrice.symbol)
            .where(and_(StockList.market.in_(markets), StockList.is_active.is_(True)))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 大盤 overview ──────────────────────────────────────
    async def get_overview_aggregates(self, market: str, as_of: date_type) -> dict[str, Any]:
        """從 stock_prices 計算「漲家數 / 跌家數 / 平盤 / 總成交量」。

        定義：
        - 漲：close > 前一日 close（用 LAG window function）— 為簡化，本實作直接用 OPEN<CLOSE 替代
          （沒前一日資料就視為平盤）。P17 真正接上 trading_calendar 後可改 LAG。
        - 簡化版讓 stock_list 為空時也回 0 而非 SQL error。

        本實作刻意保持簡單可審查；複雜邏輯放 service。
        """
        markets = _market_filter(market)
        advance_expr = func.sum(case((StockPrice.close > StockPrice.open, 1), else_=0))
        decline_expr = func.sum(case((StockPrice.close < StockPrice.open, 1), else_=0))
        unchanged_expr = func.sum(case((StockPrice.close == StockPrice.open, 1), else_=0))
        volume_expr = func.coalesce(func.sum(StockPrice.volume), 0)

        stmt = (
            select(
                advance_expr.label("advance"),
                decline_expr.label("decline"),
                unchanged_expr.label("unchanged"),
                volume_expr.label("volume"),
            )
            .join(StockList, StockList.symbol == StockPrice.symbol)
            .where(
                and_(
                    StockList.market.in_(markets),
                    # 只計 active 標的：權證已於 stock_list 停用。不濾的話漲跌家數會被權證
                    # 灌爆（實測 2026-07-15 當日 367 筆中有 300 筆是權證 = 81.7%）。
                    StockList.is_active.is_(True),
                    StockPrice.date == as_of,
                )
            )
        )
        result: Result[Any] = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return {"advance": 0, "decline": 0, "unchanged": 0, "volume": 0}
        return {
            "advance": int(row.advance or 0),
            "decline": int(row.decline or 0),
            "unchanged": int(row.unchanged or 0),
            "volume": int(row.volume or 0),
        }

    # ── 大盤指數報價（從 stock_prices 取指數 symbol 的最近兩日）────────
    async def get_index_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """取指定指數 symbols 最近 2 個交易日，算出 close + 當日漲跌%。

        指數（TAIEX / TPEX 等）以一般 OHLCV row 存於 stock_prices（symbol 即指數代號），
        不依賴 stock_list.market，故 by symbol 直接查。
        """
        if not symbols:
            return {}
        rn = (
            func.row_number()
            .over(
                partition_by=StockPrice.symbol,
                order_by=StockPrice.date.desc(),
            )
            .label("rn")
        )
        sub = (
            select(
                StockPrice.symbol.label("symbol"),
                StockPrice.date.label("date"),
                StockPrice.close.label("close"),
                StockPrice.volume.label("volume"),
                rn,
            )
            .where(StockPrice.symbol.in_(symbols))
            .subquery()
        )
        stmt = select(sub.c.symbol, sub.c.date, sub.c.close, sub.c.volume, sub.c.rn).where(
            sub.c.rn <= 2
        )
        result = await self.session.execute(stmt)

        by_symbol: dict[str, dict[int, Any]] = {}
        for r in result.all():
            by_symbol.setdefault(r.symbol, {})[int(r.rn)] = r

        out: dict[str, dict[str, Any]] = {}
        for sym, rows in by_symbol.items():
            latest = rows.get(1)
            if latest is None:
                continue
            change: Decimal | None = None
            change_pct: Decimal | None = None
            prev = rows.get(2)
            if prev is not None and prev.close not in (None, 0):
                change = Decimal(latest.close) - Decimal(prev.close)
                change_pct = (change / Decimal(prev.close) * Decimal(100)).quantize(Decimal("0.01"))
            out[sym] = {
                "close": latest.close,
                "change": change,
                "change_pct": change_pct,
                "volume": int(latest.volume or 0),
                "as_of": latest.date,
            }
        return out

    # ── 三大法人（TW only）──────────────────────────────────
    async def get_institutional_for_date(
        self,
        target_date: date_type,
        *,
        market: str = "TW",
        limit: int = 100,
    ) -> list[InstitutionalTrading]:
        markets = _market_filter(market)
        stmt = (
            select(InstitutionalTrading)
            .join(StockList, StockList.symbol == InstitutionalTrading.symbol)
            .where(
                and_(
                    StockList.market.in_(markets),
                    StockList.is_active.is_(True),
                    InstitutionalTrading.date == target_date,
                )
            )
            .order_by(InstitutionalTrading.foreign_net.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    _INST_COLS = (
        "foreign_buy",
        "foreign_sell",
        "foreign_net",
        "trust_buy",
        "trust_sell",
        "trust_net",
        "dealer_buy",
        "dealer_sell",
        "dealer_net",
    )

    _MARGIN_COLS = (
        "margin_buy",
        "margin_sell",
        "margin_balance",
        "margin_quota",
        "short_buy",
        "short_sell",
        "short_balance",
        "short_quota",
    )

    async def _chunked_upsert(
        self,
        model: Any,
        clean: list[dict[str, Any]],
        value_cols: tuple[str, ...],
        *,
        commit: bool,
    ) -> int:
        """多列 upsert（PK=(symbol,date)）並分塊送出。

        asyncpg 單條語句參數上限 32767；全市場 bulk（~2,200 檔 × 多日）一次送會爆
        （margin 每列 11 欄 → >2,900 列即超限）。以 1,000 列/塊切分，遠低於上限。
        """
        if not clean:
            return 0
        for i in range(0, len(clean), _UPSERT_CHUNK):
            chunk = clean[i : i + _UPSERT_CHUNK]
            stmt = pg_insert(model).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "date"],
                set_={c: getattr(stmt.excluded, c) for c in (*value_cols, "source")},
            )
            await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return len(clean)

    async def upsert_margin(
        self, rows: list[dict[str, Any]], *, source: str | None = None, commit: bool = False
    ) -> int:
        """融資融券每日一列 upsert。PK=(symbol, date)。"""
        if not rows:
            return 0
        clean: list[dict[str, Any]] = []
        for r in rows:
            if not r.get("symbol") or r.get("date") is None:
                continue
            entry = {"symbol": r["symbol"], "date": r["date"], "source": source}
            for c in self._MARGIN_COLS:
                entry[c] = int(r.get(c) or 0)
            clean.append(entry)
        return await self._chunked_upsert(MarginTrading, clean, self._MARGIN_COLS, commit=commit)

    async def upsert_institutional(
        self, rows: list[dict[str, Any]], *, source: str | None = None, commit: bool = False
    ) -> int:
        """把三大法人（已 pivot 的每日一列）upsert 進 institutional_trading。

        rows 為 _normalize_institutional 的 pivot 輸出 + symbol（date / foreign_* / trust_* /
        dealer_*）。PK=(symbol, date)，重複 ON CONFLICT 更新。
        """
        if not rows:
            return 0
        clean: list[dict[str, Any]] = []
        for r in rows:
            if not r.get("symbol") or r.get("date") is None:
                continue
            entry = {"symbol": r["symbol"], "date": r["date"], "source": source}
            for c in self._INST_COLS:
                entry[c] = int(r.get(c) or 0)
            clean.append(entry)
        return await self._chunked_upsert(
            InstitutionalTrading, clean, self._INST_COLS, commit=commit
        )

    async def get_latest_institutional_date(self, market: str) -> date_type | None:
        """三大法人最近一筆 date（依 market）。與 get_latest_trading_date 分開——
        法人資料盤後才出，且本地庫覆蓋日期常與股價不同，用股價日會查到空。"""
        markets = _market_filter(market)
        stmt = (
            select(func.max(InstitutionalTrading.date))
            .join(StockList, StockList.symbol == InstitutionalTrading.symbol)
            .where(StockList.market.in_(markets), StockList.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_symbols(self, market: str) -> set[str]:
        """回某 market 所有 is_active 的 symbol 集合（給即時漲跌家數過濾用）。"""
        markets = _market_filter(market)
        stmt = select(StockList.symbol).where(
            StockList.market.in_(markets), StockList.is_active.is_(True)
        )
        result = await self.session.execute(stmt)
        return {r[0] for r in result.all()}

    async def get_names_for(self, symbols: list[str]) -> dict[str, str]:
        """批次取股票中文名（symbol → name）。查無者不會出現在結果中。"""
        if not symbols:
            return {}
        stmt = select(StockList.symbol, StockList.name).where(
            StockList.symbol.in_(list(set(symbols)))
        )
        result = await self.session.execute(stmt)
        return {r.symbol: r.name for r in result.all() if r.name}

    # ── 漲跌幅 / 成交量排行 ────────────────────────────────
    async def get_movers(
        self,
        market: str,
        mover_type: str,
        *,
        as_of: date_type | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """漲跌幅排行 / 成交量排行。

        Args:
            market: TW / US
            mover_type: gainers / losers / volume
            as_of: 預設為 latest_trading_date(market)
            limit: 取前 N

        Return:
            list of dict: {symbol, name, close, change_pct, volume}
        """
        if as_of is None:
            as_of = await self.get_latest_trading_date(market)
            if as_of is None:
                return []

        markets = _market_filter(market)
        # change_pct = (close - open) / open * 100
        # 用 NULLIF(open, 0) 防除以 0
        change_pct_expr = (
            (cast(StockPrice.close, Numeric(20, 6)) - cast(StockPrice.open, Numeric(20, 6)))
            / func.nullif(cast(StockPrice.open, Numeric(20, 6)), 0)
            * literal(100)
        ).label("change_pct")

        stmt = (
            select(
                StockPrice.symbol.label("symbol"),
                StockList.name.label("name"),
                StockPrice.close.label("close"),
                change_pct_expr,
                StockPrice.volume.label("volume"),
            )
            .join(StockList, StockList.symbol == StockPrice.symbol)
            .where(
                and_(
                    StockList.market.in_(markets),
                    # 同 get_overview_aggregates：不濾 active，排行榜會塞滿權證
                    StockList.is_active.is_(True),
                    StockPrice.date == as_of,
                )
            )
        )
        mt = mover_type.lower()
        if mt == "gainers":
            stmt = stmt.order_by(change_pct_expr.desc().nullslast())
        elif mt == "losers":
            # 跌幅榜語意＝最負在前、未定義(NULL，如 open=0 停牌股) 沉底；
            # 與 gainers 的 nullslast 對稱。原用 nullsfirst 會把 NULL 排到榜首擠掉真正大跌股。
            stmt = stmt.order_by(change_pct_expr.asc().nullslast())
        elif mt == "volume":
            stmt = stmt.order_by(StockPrice.volume.desc())
        else:
            # 預設 gainers
            stmt = stmt.order_by(change_pct_expr.desc().nullslast())

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows: list[dict[str, Any]] = []
        for r in result.all():
            rows.append(
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "close": r.close,
                    "change_pct": r.change_pct,
                    "volume": int(r.volume or 0),
                }
            )
        return rows


# 抑制 unused import 警告
_ = (Date, Decimal, String, literal)


__all__ = ["MarketRepository"]

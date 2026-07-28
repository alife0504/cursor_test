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
from typing import Any, ClassVar

from sqlalchemy import (
    Date,
    Numeric,
    String,
    and_,
    cast,
    func,
    literal,
    select,
    text,
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
        """從 stock_prices 計算「漲/跌/平家數、漲停/跌停家數、總成交量」（對前一日收盤）。

        定義：
        - 漲/跌/平：close 對「前一交易日 close」（LAG）比較。原本用 open<close 只是簡化；
          漲停/跌停必須對前一日收盤才算得出，故一併改為 LAG 基準（也與盤中即時 change_rate 一致）。
        - 漲停/跌停：當日漲跌幅落在 ±9.9%～±10.5% 視為漲停/跌停。台股漲跌幅上限 ±10%，因跳動
          單位（tick）取整實際約 9.7～10%；上界 10.5% 用來排除除權息參考價調整等 >10% 的異常值
          （實測 2026-07-28 當日排掉 30 筆 <−10.5% 的非跌停）。
        - 只計 active 標的：權證已於 stock_list 停用，不濾會被灌爆。
        - 母體用「每檔最近交易日（rn=1，≤ as_of）」而非「當日 as_of」：最新交易日資料常尚未
          載完（實測 2026-07-28 只有 1899 檔、前幾日 ~2372），用當日會漏掉數百檔、家數被截；
          rn=1 補回這些檔（退用其前一交易日），也與板塊圖 get_eod_change_rows 同母體。
        """
        markets = _market_filter(market)
        rows = await self.session.execute(
            text(
                """
                WITH w AS (
                    SELECT sp.symbol, sp.date, sp.close, sp.volume,
                           LAG(sp.close) OVER (PARTITION BY sp.symbol ORDER BY sp.date) AS prev,
                           ROW_NUMBER() OVER (
                               PARTITION BY sp.symbol ORDER BY sp.date DESC
                           ) AS rn
                    FROM stock_prices sp
                    JOIN stock_list sl ON sl.symbol = sp.symbol
                    WHERE sl.is_active AND sl.market = ANY(:mk)
                      AND sp.date >= (:as_of::date - 20) AND sp.date <= :as_of
                ),
                d AS (
                    SELECT close, prev, volume,
                           (close - prev) / prev * 100.0 AS pct
                    FROM w
                    WHERE rn = 1 AND prev IS NOT NULL AND prev > 0
                )
                SELECT
                    COUNT(*) FILTER (WHERE close > prev)                        AS advance,
                    COUNT(*) FILTER (WHERE close < prev)                        AS decline,
                    COUNT(*) FILTER (WHERE close = prev)                        AS unchanged,
                    COUNT(*) FILTER (WHERE pct >= :lu_lo AND pct <= :lim_hi)    AS limit_up,
                    COUNT(*) FILTER (WHERE pct <= :ld_hi AND pct >= :lim_lo)    AS limit_down,
                    COALESCE(SUM(volume), 0)                                    AS volume
                FROM d
                """
            ),
            {
                "mk": list(markets),
                "as_of": as_of,
                "lu_lo": 9.9,
                "lim_hi": 10.5,
                "ld_hi": -9.9,
                "lim_lo": -10.5,
            },
        )
        row = rows.one_or_none()
        if row is None:
            return {
                "advance": 0,
                "decline": 0,
                "unchanged": 0,
                "limit_up": 0,
                "limit_down": 0,
                "volume": 0,
            }
        return {
            "advance": int(row.advance or 0),
            "decline": int(row.decline or 0),
            "unchanged": int(row.unchanged or 0),
            "limit_up": int(row.limit_up or 0),
            "limit_down": int(row.limit_down or 0),
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
    # 三大法人排行可依哪個淨額欄位排序（外資 / 投信 / 自營商）
    _RANK_NET_COLS: ClassVar[dict[str, Any]] = {
        "foreign": InstitutionalTrading.foreign_net,
        "trust": InstitutionalTrading.trust_net,
        "dealer": InstitutionalTrading.dealer_net,
    }

    async def get_institutional_for_date(
        self,
        target_date: date_type,
        *,
        market: str = "TW",
        limit: int = 100,
        order: str = "buy",
        by: str = "foreign",
    ) -> list[InstitutionalTrading]:
        """依某法人買賣超排序回前 N 檔。

        by ∈ foreign/trust/dealer（依哪個淨額欄位）；order="buy" → 買超最大（desc）、
        "sell" → 賣超最大（asc）。
        """
        markets = _market_filter(market)
        net_col = self._RANK_NET_COLS.get(by, InstitutionalTrading.foreign_net)
        order_col = net_col.asc() if order == "sell" else net_col.desc()
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
            .order_by(order_col)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_institutional_totals(
        self, target_date: date_type, *, market: str = "TW"
    ) -> dict[str, int]:
        """當日全市場三大法人淨額合計（股數）+ 淨額金額（元，淨股數×最新收盤）+ 有資料檔數。

        頁面 KPI 需要當日『整個市場』的總額；不可拿 list 回的 top-N 子集加總（方向會相反）。
        *_net = 股數合計；*_amount = 金額合計（元）＝ Σ(淨股數 × 最新收盤)，供「金額(億)」顯示。
        """
        markets = _market_filter(market)
        rows = await self.session.execute(
            text(
                """
                WITH lp AS (
                    SELECT DISTINCT ON (symbol) symbol, close
                    FROM stock_prices WHERE date >= (CURRENT_DATE - 20)
                    ORDER BY symbol, date DESC
                )
                SELECT
                    COALESCE(SUM(it.foreign_net), 0)                       AS f_net,
                    COALESCE(SUM(it.trust_net), 0)                         AS t_net,
                    COALESCE(SUM(it.dealer_net), 0)                        AS d_net,
                    COUNT(*)                                              AS cnt,
                    COALESCE(SUM(it.foreign_net * COALESCE(lp.close,0)),0) AS f_amt,
                    COALESCE(SUM(it.trust_net   * COALESCE(lp.close,0)),0) AS t_amt,
                    COALESCE(SUM(it.dealer_net  * COALESCE(lp.close,0)),0) AS d_amt
                FROM institutional_trading it
                JOIN stock_list sl ON sl.symbol = it.symbol
                    AND sl.is_active AND sl.market = ANY(:mk)
                LEFT JOIN lp ON lp.symbol = it.symbol
                WHERE it.date = :d
                """
            ),
            {"mk": list(markets), "d": target_date},
        )
        r = rows.one()
        return {
            "foreign_net": int(r.f_net or 0),
            "trust_net": int(r.t_net or 0),
            "dealer_net": int(r.d_net or 0),
            "count": int(r.cnt or 0),
            "foreign_amount": int(r.f_amt or 0),
            "trust_amount": int(r.t_amt or 0),
            "dealer_amount": int(r.d_amt or 0),
        }

    async def get_latest_closes(self, symbols: list[str]) -> dict[str, float]:
        """批次取每檔最新收盤（近 20 天內），供三大法人「金額(億)」= 淨股數×收盤 計算。"""
        if not symbols:
            return {}
        rows = await self.session.execute(
            text(
                """
                SELECT DISTINCT ON (symbol) symbol, close
                FROM stock_prices
                WHERE symbol = ANY(:syms) AND date >= (CURRENT_DATE - 20)
                ORDER BY symbol, date DESC
                """
            ),
            {"syms": list(set(symbols))},
        )
        return {r.symbol: float(r.close) for r in rows.all() if r.close is not None}

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

    # ── 板塊熱力圖 ──────────────────────────────────────────
    async def get_industry_map(self, market: str = "TW") -> dict[str, dict[str, str]]:
        """active 台股的 symbol → {industry, name}。產業別取 stock_info.sector（TWSE 產業分類）。

        排除 ETF/受益證券類（非產業），讓熱力圖聚焦真實產業板塊。
        """
        markets = _market_filter(market)
        rows = await self.session.execute(
            text(
                """
                SELECT si.symbol, si.sector, sl.name
                FROM stock_info si
                JOIN stock_list sl ON sl.symbol = si.symbol
                WHERE sl.is_active AND sl.market = ANY(:mk)
                  AND si.sector IS NOT NULL
                  AND si.sector NOT LIKE '%ETF%'
                  AND si.sector NOT LIKE '%ETN%'
                  AND si.sector NOT LIKE '%受益證券%'
                  AND si.sector NOT LIKE '%指數股票型%'
                """
            ),
            {"mk": list(markets)},
        )
        return {r[0]: {"industry": r[1], "name": r[2] or r[0]} for r in rows.all()}

    async def get_eod_change_rows(self, market: str = "TW") -> list[dict[str, Any]]:
        """盤後熱力圖用：每檔最新交易日 漲跌%(對前一交易日收盤) + 成交值(turnover)。

        即時快照不可用（收盤/未開通）時的 chg 模式資料來源。用 LAG 取前一日收盤。
        """
        markets = _market_filter(market)
        rows = await self.session.execute(
            text(
                """
                WITH w AS (
                    SELECT sp.symbol, sp.date, sp.close, sp.turnover,
                           LAG(sp.close) OVER (PARTITION BY sp.symbol ORDER BY sp.date) AS prev_close,
                           ROW_NUMBER() OVER (PARTITION BY sp.symbol ORDER BY sp.date DESC) AS rn
                    FROM stock_prices sp
                    JOIN stock_list sl ON sl.symbol = sp.symbol
                    WHERE sl.is_active AND sl.market = ANY(:mk)
                      AND sp.date >= (CURRENT_DATE - 20)
                )
                SELECT symbol, close, prev_close, turnover
                FROM w WHERE rn = 1 AND prev_close IS NOT NULL AND prev_close <> 0
                """
            ),
            {"mk": list(markets)},
        )
        out: list[dict[str, Any]] = []
        for r in rows.all():
            close = float(r.close) if r.close is not None else None
            prev = float(r.prev_close)
            if close is None:
                continue
            out.append(
                {
                    "symbol": r.symbol,
                    "metric": round((close - prev) / prev * 100, 2),
                    "value": float(r.turnover or 0),
                }
            )
        return out

    async def get_flow_rows(self, market: str = "TW") -> list[dict[str, Any]]:
        """資金流模式：每檔 三大法人當日淨買賣超「金額」(億) = 淨股數 × 最新收盤 / 1e8。

        institutional 的 *_net 是股數；乘最新收盤估算金額。value(格子大小) 用成交值。
        """
        markets = _market_filter(market)
        rows = await self.session.execute(
            text(
                """
                WITH lp AS (
                    SELECT DISTINCT ON (symbol) symbol, close, turnover
                    FROM stock_prices
                    WHERE date >= (CURRENT_DATE - 20)
                    ORDER BY symbol, date DESC
                ),
                li AS (  -- 每檔各自最近一日三大法人（近日部分覆蓋 → 不可用全域 max(date)，
                         -- 否則只到前一日的個股會被漏掉、資金流誤顯示為 0）
                    SELECT DISTINCT ON (symbol) symbol, foreign_net, trust_net, dealer_net
                    FROM institutional_trading
                    WHERE date >= (CURRENT_DATE - 10)
                    ORDER BY symbol, date DESC
                )
                SELECT li.symbol,
                       (li.foreign_net + li.trust_net + li.dealer_net)::numeric
                           * COALESCE(lp.close, 0) / 100000000.0 AS flow_yi,
                       COALESCE(lp.turnover, 0) AS turnover
                FROM li
                JOIN stock_list sl ON sl.symbol = li.symbol
                    AND sl.is_active AND sl.market = ANY(:mk)
                LEFT JOIN lp ON lp.symbol = li.symbol
                """
            ),
            {"mk": list(markets)},
        )
        return [
            {
                "symbol": r.symbol,
                "metric": round(float(r.flow_yi or 0), 2),
                "value": float(r.turnover or 0),
            }
            for r in rows.all()
        ]

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

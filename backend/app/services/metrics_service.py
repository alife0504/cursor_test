"""MetricsService —— 刷新 stock_metrics 每檔最新指標快照（選股篩選器用）。

指標與來源：
- pe_ratio / pbr / dividend_yield：FinMind TaiwanStockPER
  （本地庫 bronze.taiwan_stock_per 取每檔最新；近日缺口用 API bulk 覆蓋更新）。
- market_cap：FinMind TaiwanStockMarketValue（bronze.taiwan_stock_market_value）。
- rsi14：app stock_prices 近 N 日收盤計算（reuse screening_service._rsi）。
- eps_growth：financial_statements 最新一季 EPS 對去年同季 YoY (%)。

只保留最新快照（symbol PK），由每日排程 sync_stock_metrics_tw 刷新。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.price import StockPrice
from app.models.stock import StockList
from app.models.tw_specific import StockMetrics
from app.services.screening_service import _rsi

logger = get_logger(__name__)

_METRIC_COLS = (
    "as_of_date",
    "pe_ratio",
    "pbr",
    "dividend_yield",
    "market_cap",
    "rsi14",
    "eps_growth",
)


def _dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d.is_finite() else None


def _pos_dec(v: Any) -> Decimal | None:
    """本益比 / 淨值比專用：FinMind 對虧損/無資料回 PER=0（或負），非有效估值 → 視為 None。

    否則「PE ≤ 15」會把 PE=0 的虧損股也選進來，誤導價值型篩選。殖利率 0 是合法（無配息）
    故不套此規則。
    """
    d = _dec(v)
    return d if (d is not None and d > 0) else None


class MetricsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sync_stock_metrics(
        self, *, rsi_days: int = 40, per_gap_days: int = 10, use_api: bool = True
    ) -> dict[str, int]:
        """重算全市場（active TWSE/TPEX）最新指標並 upsert stock_metrics。"""
        active = await self._active_symbols()
        if not active:
            return {"symbols": 0, "written": 0}

        per = await self._latest_per(active, gap_days=per_gap_days, use_api=use_api)
        mv = await self._latest_market_value(active, gap_days=per_gap_days, use_api=use_api)
        rsi = await self._compute_rsi(active, days=rsi_days)
        epsg = await self._eps_growth(active)

        rows: list[dict[str, Any]] = []
        for sym in active:
            p = per.get(sym)
            m = mv.get(sym)
            as_of = None
            if p and p.get("date"):
                as_of = p["date"]
            elif m and m.get("date"):
                as_of = m["date"]
            rows.append(
                {
                    "symbol": sym,
                    "as_of_date": as_of,
                    "pe_ratio": p.get("pe_ratio") if p else None,
                    "pbr": p.get("pbr") if p else None,
                    "dividend_yield": p.get("dividend_yield") if p else None,
                    "market_cap": m.get("market_cap") if m else None,
                    "rsi14": rsi.get(sym),
                    "eps_growth": epsg.get(sym),
                }
            )
        written = await self._upsert(rows)
        logger.info(
            "metrics.sync.done",
            symbols=len(active),
            with_pe=sum(1 for r in rows if r["pe_ratio"] is not None),
            with_mktcap=sum(1 for r in rows if r["market_cap"] is not None),
            with_rsi=sum(1 for r in rows if r["rsi14"] is not None),
            with_epsg=sum(1 for r in rows if r["eps_growth"] is not None),
            written=written,
        )
        return {"symbols": len(active), "written": written}

    # ── active symbols ─────────────────────────────────────
    async def _active_symbols(self) -> list[str]:
        rows = await self.session.execute(
            select(StockList.symbol).where(
                StockList.is_active.is_(True),
                StockList.market.in_(("TWSE", "TPEX")),
            )
        )
        return [r[0] for r in rows.all()]

    # ── 本地庫連線 ─────────────────────────────────────────
    @staticmethod
    async def _local_conn():
        import asyncpg

        pw = settings.FINMIND_LOCAL_PASSWORD
        return await asyncpg.connect(
            host=settings.FINMIND_LOCAL_HOST,
            port=settings.FINMIND_LOCAL_PORT,
            user=settings.FINMIND_LOCAL_USER,
            password=pw.get_secret_value() if pw else None,
            database=settings.FINMIND_LOCAL_DB,
            timeout=30,
        )

    # ── PER / 殖利率 / PBR ─────────────────────────────────
    async def _latest_per(
        self, active: list[str], *, gap_days: int, use_api: bool
    ) -> dict[str, dict[str, Any]]:
        active_set = set(active)
        out: dict[str, dict[str, Any]] = {}
        # 1) 本地庫每檔最新
        try:
            conn = await self._local_conn()
            try:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (stock_id) stock_id, date, "PER", "PBR", dividend_yield
                    FROM bronze.taiwan_stock_per
                    ORDER BY stock_id, date DESC
                    """
                )
            finally:
                await conn.close()
            for r in rows:
                sid = r["stock_id"]
                if sid not in active_set:
                    continue
                out[sid] = {
                    "date": r["date"],
                    "pe_ratio": _pos_dec(r["PER"]),
                    "pbr": _pos_dec(r["PBR"]),
                    "dividend_yield": _dec(r["dividend_yield"]),
                }
        except Exception:
            logger.warning("metrics.per.local_failed", exc_info=True)

        # 2) API bulk 近日覆蓋（較新的資料日勝出）
        if use_api and settings.FINMIND_TOKEN is not None:
            try:
                from app.data_sources.tw.finmind_source import FinMindSource

                end = datetime.now(UTC).date()
                start = end - timedelta(days=gap_days)
                api_rows = await FinMindSource(settings).fetch_all_per(start, end)
                for r in api_rows:
                    sid = r["symbol"]
                    if sid not in active_set:
                        continue
                    prev = out.get(sid)
                    if prev is None or (prev.get("date") and r["date"] >= prev["date"]):
                        out[sid] = {
                            "date": r["date"],
                            "pe_ratio": _pos_dec(r.get("pe_ratio")),
                            "pbr": _pos_dec(r.get("pbr")),
                            "dividend_yield": _dec(r.get("dividend_yield")),
                        }
            except Exception:
                logger.warning("metrics.per.api_failed", exc_info=True)
        return out

    # ── 市值 ───────────────────────────────────────────────
    async def _latest_market_value(
        self, active: list[str], *, gap_days: int, use_api: bool
    ) -> dict[str, dict[str, Any]]:
        active_set = set(active)
        out: dict[str, dict[str, Any]] = {}
        try:
            conn = await self._local_conn()
            try:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (stock_id) stock_id, date, market_value
                    FROM bronze.taiwan_stock_market_value
                    ORDER BY stock_id, date DESC
                    """
                )
            finally:
                await conn.close()
            for r in rows:
                sid = r["stock_id"]
                if sid not in active_set:
                    continue
                mv = r["market_value"]
                out[sid] = {"date": r["date"], "market_cap": int(mv) if mv is not None else None}
        except Exception:
            logger.warning("metrics.mktcap.local_failed", exc_info=True)

        if use_api and settings.FINMIND_TOKEN is not None:
            try:
                from app.data_sources.tw.finmind_source import FinMindSource

                end = datetime.now(UTC).date()
                start = end - timedelta(days=gap_days)
                api_rows = await FinMindSource(settings).fetch_all_market_value(start, end)
                for r in api_rows:
                    sid = r["symbol"]
                    if sid not in active_set:
                        continue
                    prev = out.get(sid)
                    if prev is None or (prev.get("date") and r["date"] >= prev["date"]):
                        out[sid] = {"date": r["date"], "market_cap": r.get("market_cap")}
            except Exception:
                logger.warning("metrics.mktcap.api_failed", exc_info=True)
        return out

    # ── RSI14（app stock_prices）────────────────────────────
    async def _compute_rsi(self, active: list[str], *, days: int) -> dict[str, Decimal]:
        active_set = set(active)
        cutoff = datetime.now(UTC).date() - timedelta(days=days)
        # 一次撈近 N 日全市場收盤，Python 端分組算 RSI（避免逐檔查詢）
        rows = await self.session.execute(
            select(StockPrice.symbol, StockPrice.date, StockPrice.close)
            .where(StockPrice.date >= cutoff)
            .order_by(StockPrice.symbol, StockPrice.date)
        )
        by_sym: dict[str, list[float]] = {}
        for sym, _d, close in rows.all():
            if sym not in active_set or close is None:
                continue
            by_sym.setdefault(sym, []).append(float(close))
        out: dict[str, Decimal] = {}
        for sym, closes in by_sym.items():
            val = _rsi(closes, 14)
            if val is not None:
                out[sym] = Decimal(str(round(val, 2)))
        return out

    # ── EPS YoY 成長（financial_statements）─────────────────
    async def _eps_growth(self, active: list[str]) -> dict[str, Decimal]:
        active_set = set(active)
        # 撈每檔各季 EPS（只季報 fq 1~4、eps 非空），Python 端算最新季 vs 去年同季
        rows = await self.session.execute(
            text(
                """
                SELECT symbol, fiscal_year, fiscal_quarter, eps
                FROM financial_statements
                WHERE eps IS NOT NULL AND fiscal_quarter BETWEEN 1 AND 4
                """
            )
        )
        eps_map: dict[str, dict[tuple[int, int], Decimal]] = {}
        for sym, fy, fq, eps in rows.all():
            if sym not in active_set or eps is None:
                continue
            eps_map.setdefault(sym, {})[(int(fy), int(fq))] = Decimal(str(eps))

        out: dict[str, Decimal] = {}
        for sym, quarters in eps_map.items():
            if not quarters:
                continue
            latest = max(quarters)  # (fy, fq)
            prior_key = (latest[0] - 1, latest[1])
            cur = quarters[latest]
            prev = quarters.get(prior_key)
            if prev is None or prev == 0:
                continue
            growth = (cur - prev) / abs(prev) * Decimal("100")
            # 夾限到欄位精度可容範圍，避免極端值溢位 Numeric(12,4)
            if growth.copy_abs() > Decimal("99999999"):
                continue
            out[sym] = growth.quantize(Decimal("0.0001"))
        return out

    # ── upsert ─────────────────────────────────────────────
    async def _upsert(self, rows: list[dict[str, Any]]) -> int:
        rows = [r for r in rows if r.get("symbol")]
        if not rows:
            return 0
        written = 0
        for i in range(0, len(rows), 1000):
            chunk = rows[i : i + 1000]
            stmt = pg_insert(StockMetrics).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    **{c: getattr(stmt.excluded, c) for c in _METRIC_COLS},
                    "updated_at": text("NOW()"),
                },
            )
            await self.session.execute(stmt)
            written += len(chunk)
        await self.session.commit()
        return written


__all__ = ["MetricsService"]

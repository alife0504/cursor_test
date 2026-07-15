"""FinancialsRepository — financial_statements + monthly_revenue CRUD。

依 PLAN.md 第 10.4 章「財報」+ 第 20.2 章。

提供：
- upsert_statements(rows): IS/BS/CF bulk upsert（PK = symbol/year/quarter/type）
- list_statements(symbol, year, quarter)
- upsert_monthly_revenue(rows): 月營收 upsert（PK = symbol/year/month）
- list_monthly_revenue(symbol, year)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging_config import get_logger
from app.models.financials import FinancialStatement
from app.models.tw_specific import MonthlyRevenue
from app.repos.base import BaseRepository

logger = get_logger(__name__)

# financial_statements 的 11 個金額 typed 欄位（IS/BS/CF 合計）——
# upsert 時一律填齊（缺值 None）以保 pg_insert 多列 VALUES 欄位一致。
_STATEMENT_MONEY_COLS: tuple[str, ...] = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "operating_cashflow",
    "investing_cashflow",
    "financing_cashflow",
)


class FinancialsRepository(BaseRepository):
    # ── financial_statements ──────────────────────────────

    async def list_statements(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
        statement_type: str | None = None,
    ) -> list[FinancialStatement]:
        stmt = select(FinancialStatement).where(FinancialStatement.symbol == symbol)
        if year is not None:
            stmt = stmt.where(FinancialStatement.fiscal_year == year)
        if quarter is not None:
            stmt = stmt.where(FinancialStatement.fiscal_quarter == quarter)
        if statement_type is not None:
            stmt = stmt.where(FinancialStatement.statement_type == statement_type)
        stmt = stmt.order_by(
            FinancialStatement.fiscal_year.desc(),
            FinancialStatement.fiscal_quarter.desc(),
            FinancialStatement.statement_type,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_statements(self, rows: list[dict[str, Any]], *, commit: bool = False) -> int:
        """ON CONFLICT (symbol, fiscal_year, fiscal_quarter, statement_type) DO UPDATE。

        Each row: {symbol, fiscal_year, fiscal_quarter, statement_type, ...optional money cols...,
                   payload, announced_at, source}
        """
        if not rows:
            return 0
        clean: list[dict[str, Any]] = []
        for r in rows:
            if not all(
                k in r and r[k] is not None
                for k in ("symbol", "fiscal_year", "fiscal_quarter", "statement_type")
            ):
                continue
            entry: dict[str, Any] = {
                "symbol": r["symbol"],
                "fiscal_year": int(r["fiscal_year"]),
                "fiscal_quarter": int(r["fiscal_quarter"]),
                "statement_type": r["statement_type"],
                "payload": r.get("payload"),
                "announced_at": r.get("announced_at"),
                "source": r.get("source"),
            }
            # 一律填齊所有 typed 欄位（缺值填 None）——pg_insert().values(list) 要求每列
            # 欄位集合一致；IS/BS/CF 各自只有部分欄位，若條件式加 key 會導致 VALUES 異質而
            # 觸發 CompileError（explicitly rendered as boundparameter）。
            for col in _STATEMENT_MONEY_COLS:
                entry[col] = _ensure_decimal(r.get(col))
            clean.append(entry)

        if not clean:
            return 0

        stmt = pg_insert(FinancialStatement).values(clean)
        update_set: dict[str, Any] = {
            "payload": stmt.excluded.payload,
            "announced_at": stmt.excluded.announced_at,
            "source": stmt.excluded.source,
        }
        for col in _STATEMENT_MONEY_COLS:
            update_set[col] = getattr(stmt.excluded, col)

        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "fiscal_year", "fiscal_quarter", "statement_type"],
            set_=update_set,
        )
        await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return len(clean)

    # ── monthly_revenue ───────────────────────────────────

    async def list_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[MonthlyRevenue]:
        stmt = select(MonthlyRevenue).where(MonthlyRevenue.symbol == symbol)
        if year is not None:
            stmt = stmt.where(MonthlyRevenue.year == year)
        stmt = stmt.order_by(MonthlyRevenue.year.desc(), MonthlyRevenue.month.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_monthly_revenue(
        self, rows: list[dict[str, Any]], *, commit: bool = False
    ) -> int:
        if not rows:
            return 0
        clean: list[dict[str, Any]] = []
        for r in rows:
            if not r.get("symbol") or r.get("year") is None or r.get("month") is None:
                continue
            if r.get("revenue") is None:
                continue
            entry = {
                "symbol": r["symbol"],
                "year": int(r["year"]),
                "month": int(r["month"]),
                "revenue": _ensure_decimal(r["revenue"]),
                "revenue_mom": _ensure_decimal(r.get("revenue_mom")),
                "revenue_yoy": _ensure_decimal(r.get("revenue_yoy")),
                "ytd_revenue": _ensure_decimal(r.get("ytd_revenue")),
                "ytd_yoy": _ensure_decimal(r.get("ytd_yoy")),
                "announced_at": r.get("announced_at"),
                "source": r.get("source"),
            }
            clean.append(entry)

        if not clean:
            return 0

        stmt = pg_insert(MonthlyRevenue).values(clean)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "year", "month"],
            set_={
                "revenue": stmt.excluded.revenue,
                "revenue_mom": stmt.excluded.revenue_mom,
                "revenue_yoy": stmt.excluded.revenue_yoy,
                "ytd_revenue": stmt.excluded.ytd_revenue,
                "ytd_yoy": stmt.excluded.ytd_yoy,
                "announced_at": stmt.excluded.announced_at,
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
        if isinstance(v, float) and v != v:
            return None
        return Decimal(str(v))
    if isinstance(v, str):
        s = v.strip().replace(",", "").replace("%", "")
        if not s:
            return None
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


__all__ = ["FinancialsRepository"]

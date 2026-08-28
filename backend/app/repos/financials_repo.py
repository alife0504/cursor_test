"""FinancialsRepository — financial_statements + monthly_revenue CRUD。

依 PLAN.md 第 10.4 章「財報」+ 第 20.2 章。

提供：
- upsert_statements(rows): IS/BS/CF bulk upsert（PK = symbol/year/quarter/type）
- list_statements(symbol, year, quarter)
- upsert_monthly_revenue(rows): 月營收 upsert（PK = symbol/year/month）
- list_monthly_revenue(symbol, year)
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging_config import get_logger
from app.domain.disclosure_calendar import (
    FilerCategory,
    monthly_revenue_deadline,
    statement_deadline,
)
from app.domain.filer_classification import filer_category_for
from app.models.financials import FinancialStatement
from app.models.stock import StockList
from app.models.tw_specific import MonthlyRevenue
from app.repos.base import BaseRepository

logger = get_logger(__name__)


def _safe_statement_deadline(
    fiscal_year: int,
    fiscal_quarter: int,
    category: FilerCategory = FilerCategory.INSURER,
) -> date_type | None:
    """算財報法定期限；資料異常（如 quarter 超出 1~4）不該讓整批 upsert 掛掉。

    ⚠️ category 預設 **INSURER 而非 GENERAL**：金融保險 Q2 是 8/31、一般是 8/14，
    套錯成 GENERAL 會寫入**過早**的期限 → PIT 邊界提早開放 → 偷看未來 18 天。
    未知時取期限最晚者才安全（見 app.domain.filer_classification）。
    """
    try:
        return statement_deadline(fiscal_year, fiscal_quarter, category=category)
    except (ValueError, TypeError):
        logger.warning(
            "financials.deadline.skip", fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter
        )
        return None


def _safe_monthly_revenue_deadline(
    year: int,
    month: int,
    category: FilerCategory = FilerCategory.INSURER,
) -> date_type | None:
    """算月營收法定期限；月份異常時回 None 而非中斷。

    ⚠️ category 預設 INSURER：保險業自 2026 起月營收得延至 15 日，套成 GENERAL(10 日)
    會偷看未來 5 天。
    """
    try:
        return monthly_revenue_deadline(year, month, category=category)
    except (ValueError, TypeError):
        logger.warning("monthly_revenue.deadline.skip", year=year, month=month)
        return None


def _rev_deadline(row: dict[str, Any], cats: dict[str, FilerCategory | None]) -> date_type | None:
    """月營收法定期限；非台股（cat 為 None）不套台灣期限。"""
    cat = cats.get(row["symbol"], FilerCategory.INSURER)
    if cat is None:
        return None
    return _safe_monthly_revenue_deadline(int(row["year"]), int(row["month"]), cat)


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

    #: 適用台灣證交法 §36 期限的市場。其餘（美股等）另有各自法規，不可套用。
    _TW_MARKETS = ("TWSE", "TPEX")

    async def _filer_categories(self, symbols: list[str]) -> dict[str, FilerCategory | None]:
        """批次取 symbol → FilerCategory（依 stock_list.industry）。

        回傳值語意：
          - FilerCategory：台股，且已知該用哪組期限
          - None：**非台股**（美股等）——台灣 §36 不適用，故不可算期限，
            應寫 NULL 讓 PIT 查詢直接排除，而不是套上事實上錯誤的台灣期限。
            （美股需另接 SEC 期限：10-Q 40/45 日、10-K 60/75/90 日，屬後續工作。）
          - 不在結果中：stock_list 查無此 symbol → caller 退回保守預設（INSURER）

        期限算晚只是保守，算早就是偷看未來。
        """
        if not symbols:
            return {}
        rows = (
            await self.session.execute(
                select(
                    StockList.symbol, StockList.market, StockList.industry, StockList.name
                ).where(StockList.symbol.in_(list(set(symbols))))
            )
        ).all()
        return {
            r.symbol: (
                # 帶入 name 以識別第一上市(櫃)/KY 股（Q2 期限 8/31，修 17 天 look-ahead）
                filer_category_for(r.industry, r.name) if r.market in self._TW_MARKETS else None
            )
            for r in rows
        }

    async def upsert_statements(self, rows: list[dict[str, Any]], *, commit: bool = False) -> int:
        """ON CONFLICT (symbol, fiscal_year, fiscal_quarter, statement_type) DO UPDATE。

        Each row: {symbol, fiscal_year, fiscal_quarter, statement_type, ...optional money cols...,
                   payload, announced_at, source}
        """
        if not rows:
            return 0
        # 先濾出有效列再查類別：全部無效時就不該白跑一次 DB query
        valid = [
            r
            for r in rows
            if all(
                k in r and r[k] is not None
                for k in ("symbol", "fiscal_year", "fiscal_quarter", "statement_type")
            )
        ]
        if not valid:
            return 0
        cats = await self._filer_categories([r["symbol"] for r in valid])
        clean: list[dict[str, Any]] = []
        for r in valid:
            fy, fq = int(r["fiscal_year"]), int(r["fiscal_quarter"])
            # 查不到產業別 → INSURER（保守：期限最晚，不會偷看未來）
            # 明確為 None → 非台股，台灣 §36 不適用 → 不算期限（PIT 查詢會排除該列）
            cat = cats.get(r["symbol"], FilerCategory.INSURER)
            deadline = _safe_statement_deadline(fy, fq, cat) if cat is not None else None
            entry: dict[str, Any] = {
                "symbol": r["symbol"],
                "fiscal_year": fy,
                "fiscal_quarter": fq,
                "statement_type": r["statement_type"],
                "payload": r.get("payload"),
                # 實際公告日：上游不給 → 通常為 None。絕不用期限頂替（見 model docstring）
                "announced_at": r.get("announced_at"),
                # 法定期限：純計算，寫入時就算好，PIT 查詢才有邊界可用
                "disclosure_deadline": r.get("disclosure_deadline") or deadline,
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
            # 只在來源提供非 NULL 時才覆寫 announced_at：FinMind 恆給 NULL，若無條件覆寫，
            # 未來接 MOPS 回填的真公告日會在每晚例行 re-sync 被抹回 NULL（PIT 自動升級失效）。
            "announced_at": func.coalesce(
                stmt.excluded.announced_at, FinancialStatement.announced_at
            ),
            "disclosure_deadline": stmt.excluded.disclosure_deadline,
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
        valid = [
            r
            for r in rows
            if r.get("symbol")
            and r.get("year") is not None
            and r.get("month") is not None
            and r.get("revenue") is not None
        ]
        if not valid:
            return 0
        cats = await self._filer_categories([r["symbol"] for r in valid])
        clean: list[dict[str, Any]] = []
        for r in valid:
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
                "disclosure_deadline": r.get("disclosure_deadline") or _rev_deadline(r, cats),
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
                # 成長率（mom/yoy/ytd）：FinMind 同步只給原始 revenue，這四欄恆為 None →
                # 若無條件覆寫會把 derive_monthly_revenue_growth_tw 已算好的成長率就地抹成 NULL
                # （與同檔 announced_at 的保護不一致的漏洞）。改用 coalesce：來源有值才覆寫，
                # 否則保留既有衍生值，避免每次同步後到次月衍生前整段 NULL。
                "revenue_mom": func.coalesce(stmt.excluded.revenue_mom, MonthlyRevenue.revenue_mom),
                "revenue_yoy": func.coalesce(stmt.excluded.revenue_yoy, MonthlyRevenue.revenue_yoy),
                "ytd_revenue": func.coalesce(stmt.excluded.ytd_revenue, MonthlyRevenue.ytd_revenue),
                "ytd_yoy": func.coalesce(stmt.excluded.ytd_yoy, MonthlyRevenue.ytd_yoy),
                # 同 upsert_statements：真公告日只在來源非 NULL 時覆寫，避免被例行 re-sync 抹除
                "announced_at": func.coalesce(
                    stmt.excluded.announced_at, MonthlyRevenue.announced_at
                ),
                # 補上 disclosure_deadline（原遺漏，與 upsert_statements 不一致）：category 變動時
                # re-upsert 才會刷新法定期限，避免舊邊界殘留（反向 GENERAL→INSURER 會偏早=lookahead）。
                "disclosure_deadline": stmt.excluded.disclosure_deadline,
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

"""回填 financial_statements / monthly_revenue 的 disclosure_deadline（PIT 正確性）。

為什麼需要：
    實測兩表的 announced_at **100% 為 NULL**（上游 FinMind 不提供財報公告日）。
    沒有公告日就沒有 point-in-time 邊界 → 4 月的分析讀得到 5/15 才公告的 Q1 財報＝偷看未來。
    本腳本用 app.domain.disclosure_calendar 依證交法 §36 推算「法定最晚公告期限」回填，
    純計算、不需任何外部資料源，故可重複執行（idempotent）。

    ⚠️ 期限 ≠ 公告日。本腳本**只寫 disclosure_deadline，絕不碰 announced_at**。

用法（從 backend/ 執行；容器映像不含 scripts 以外的 migrations，故在主機跑）：
    cd backend && PYTHONPATH=. uv run python scripts/backfill_disclosure_deadline.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.domain.disclosure_calendar import (
    FilerCategory,
    monthly_revenue_deadline,
    statement_deadline,
)
from app.domain.filer_classification import SQL_FILER_CATEGORY_EXPR

# 逐 (期別 × 申報人類別) 更新。**必須分類別**：金融保險 Q2 是 8/31、一般是 8/14，
# 全部套 GENERAL 會對金融股寫入過早的期限 → 偷看未來 18 天（見 filer_classification）。
# 類別在 DB 端用子查詢判定；stock_list 查無該 symbol 時取 'insurer'（保守）。
_CAT = (
    # 內插的是本模組常數而非使用者輸入；期限/類別值仍走 bind param（故下行抑制 S608）
    f"COALESCE((SELECT {SQL_FILER_CATEGORY_EXPR} FROM stock_list s"  # noqa: S608
    " WHERE s.symbol = f.symbol), 'insurer')"
)

_STMT_SQL = text(
    f"""
    UPDATE financial_statements f
       SET disclosure_deadline = :deadline
     WHERE f.fiscal_year = :year AND f.fiscal_quarter = :quarter
       AND {_CAT} = :category
       AND f.disclosure_deadline IS DISTINCT FROM :deadline
    """  # noqa: S608 — 內插的是本模組常數，非使用者輸入
)
_REV_SQL = text(
    f"""
    UPDATE monthly_revenue f
       SET disclosure_deadline = :deadline
     WHERE f.year = :year AND f.month = :month
       AND {_CAT} = :category
       AND f.disclosure_deadline IS DISTINCT FROM :deadline
    """  # noqa: S608 — 同上
)

#: 要逐一套用的類別。GENERAL 與 INSURER 的期限不同故必須分開跑。
_CATEGORIES: tuple[tuple[str, FilerCategory], ...] = (
    ("general", FilerCategory.GENERAL),
    ("insurer", FilerCategory.INSURER),
)


async def main(dry_run: bool) -> None:
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            # 先問實際存在哪些期別，不要盲目掃全年份範圍
            fs_periods = (
                await session.execute(
                    text(
                        "SELECT DISTINCT fiscal_year, fiscal_quarter FROM financial_statements"
                        " ORDER BY 1, 2"
                    )
                )
            ).all()
            rev_periods = (
                await session.execute(
                    text("SELECT DISTINCT year, month FROM monthly_revenue ORDER BY 1, 2")
                )
            ).all()

            print(f"財報期別 {len(fs_periods)} 組、月營收期別 {len(rev_periods)} 組")

            fs_total = 0
            for year, quarter in fs_periods:
                for cat_sql, cat in _CATEGORIES:
                    try:
                        deadline = statement_deadline(int(year), int(quarter), category=cat)
                    except (ValueError, TypeError) as exc:
                        print(f"  [skip] {year}Q{quarter} {cat_sql}: {exc}")
                        continue
                    if dry_run:
                        print(f"  [dry-run] {year}Q{quarter} {cat_sql} → {deadline}")
                        continue
                    res = await session.execute(
                        _STMT_SQL,
                        {
                            "deadline": deadline,
                            "year": int(year),
                            "quarter": int(quarter),
                            "category": cat_sql,
                        },
                    )
                    fs_total += res.rowcount or 0

            rev_total = 0
            for year, month in rev_periods:
                for cat_sql, cat in _CATEGORIES:
                    try:
                        deadline = monthly_revenue_deadline(int(year), int(month), category=cat)
                    except (ValueError, TypeError) as exc:
                        print(f"  [skip] {year}-{month} {cat_sql}: {exc}")
                        continue
                    if dry_run:
                        continue
                    res = await session.execute(
                        _REV_SQL,
                        {
                            "deadline": deadline,
                            "year": int(year),
                            "month": int(month),
                            "category": cat_sql,
                        },
                    )
                    rev_total += res.rowcount or 0

            if dry_run:
                print("dry-run：未寫入")
                return

            await session.commit()
            print(
                f"[done] financial_statements 更新 {fs_total} 列、"
                f"monthly_revenue 更新 {rev_total} 列"
            )

            # 驗收：期限不可為空，且**絕不可早於該期期末**——早於期末代表算錯，
            # 那會讓 PIT 邊界比事實更早開放 = 偷看未來。期末：Q1 3/31、Q2 6/30、
            # Q3 9/30、Q4(年報) 12/31。
            bad = (
                await session.execute(
                    text(
                        """
                        SELECT count(*) FROM financial_statements
                         WHERE disclosure_deadline IS NULL
                            OR disclosure_deadline < make_date(
                                   fiscal_year,
                                   CASE fiscal_quarter
                                        WHEN 1 THEN 3 WHEN 2 THEN 6
                                        WHEN 3 THEN 9 ELSE 12 END,
                                   CASE fiscal_quarter
                                        WHEN 1 THEN 31 WHEN 2 THEN 30
                                        WHEN 3 THEN 30 ELSE 31 END)
                        """
                    )
                )
            ).scalar_one()
            null_rev = (
                await session.execute(
                    text("SELECT count(*) FROM monthly_revenue WHERE disclosure_deadline IS NULL")
                )
            ).scalar_one()
            print(f"驗收：financial 異常 {bad} 列、monthly_revenue 未填 {null_rev} 列")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印不寫")
    args = ap.parse_args()
    asyncio.run(main(args.dry_run))

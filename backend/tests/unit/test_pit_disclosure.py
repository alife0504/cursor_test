"""PIT（point-in-time）正確性：財報只能在「已公開」之後才看得到。

為什麼要有這組測試：
    財報期末 ≠ 可得日。Q1 期間 2026-03-31 結束，但依證交法 §36 法定 2026-05-15 才公告。
    若 4 月的分析讀得到 Q1 數字＝**偷看未來**，回測會系統性高估。
    這類錯誤**不會報錯**（與存活者偏誤、CF 累計基準同類），只能靠測試釘住。

    上游 FinMind 不提供實際公告日（announced_at 實測 100% NULL），故以法定期限
    disclosure_deadline 當 PIT 邊界。期限 ≠ 公告日，兩者分欄存放，查詢用
    COALESCE(announced_at, disclosure_deadline)。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.disclosure_calendar import monthly_revenue_deadline, statement_deadline
from app.repos.financials_repo import (
    _safe_monthly_revenue_deadline,
    _safe_statement_deadline,
)

pytestmark = pytest.mark.unit


# ── 寫入路徑：upsert 時就把法定期限算好 ──────────────────


def test_statement_deadline_helper_matches_domain() -> None:
    """repo 的 helper 必須與 domain 模組一致（不可自己另算一套）。"""
    for fy, fq in ((2026, 1), (2026, 2), (2026, 3), (2025, 4)):
        assert _safe_statement_deadline(fy, fq) == statement_deadline(fy, fq)


def test_monthly_revenue_deadline_helper_matches_domain() -> None:
    for y, m in ((2026, 1), (2026, 6), (2026, 12)):
        assert _safe_monthly_revenue_deadline(y, m) == monthly_revenue_deadline(y, m)


@pytest.mark.parametrize("bad_quarter", [0, 5, -1, 99])
def test_bad_quarter_returns_none_not_crash(bad_quarter: int) -> None:
    """資料異常不該讓整批 upsert 掛掉——回 None（該列就不會被 PIT 查詢看到）。"""
    assert _safe_statement_deadline(2026, bad_quarter) is None


@pytest.mark.parametrize("bad_month", [0, 13, -1])
def test_bad_month_returns_none_not_crash(bad_month: int) -> None:
    assert _safe_monthly_revenue_deadline(2026, bad_month) is None


# ── 核心不變式：期限絕不可早於期末（早於＝偷看未來）──────


_PERIOD_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


@pytest.mark.parametrize("fiscal_year", [2020, 2023, 2025, 2026])
@pytest.mark.parametrize("fiscal_quarter", [1, 2, 3, 4])
def test_deadline_never_earlier_than_period_end(fiscal_year: int, fiscal_quarter: int) -> None:
    """最重要的不變式：資料要到期末才存在，期限必定 >= 期末。

    若期限早於期末，PIT 邊界會比事實更早開放 → 偷看未來。
    """
    month, day = _PERIOD_END[fiscal_quarter]
    period_end = date(fiscal_year, month, day)
    assert statement_deadline(fiscal_year, fiscal_quarter) >= period_end


@pytest.mark.parametrize("year", [2024, 2026])
@pytest.mark.parametrize("month", list(range(1, 13)))
def test_monthly_revenue_deadline_after_month_end(year: int, month: int) -> None:
    """月營收期限必在該月結束之後（法定次月 10 日前）。"""
    deadline = monthly_revenue_deadline(year, month)
    # 該月最後一天
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    assert deadline >= end


# ── 具體對照：用真實已知日期釘住（非自我一致檢查）──────


def test_known_real_deadlines() -> None:
    """對照市場實務的真實日期，而非只驗內部自洽。"""
    # 一般公司 45 日制
    assert statement_deadline(2025, 1) == date(2025, 5, 15)
    assert statement_deadline(2025, 3) == date(2025, 11, 14)
    # 2024 年報 → 2025-03-31（週一，不需順延）
    assert statement_deadline(2024, 4) == date(2025, 3, 31)


def test_weekend_rollforward_is_applied() -> None:
    """期限落在週末必須往後順延——順延方向是往後，對 PIT 而言更保守（更晚才知道）。"""
    # 2026-05-10 是週日 → 月營收期限順延至 5/11（週一）
    d = monthly_revenue_deadline(2026, 4)
    assert d == date(2026, 5, 11)
    assert d.weekday() < 5

    # 2026-11-14 是週六 → Q3 期限順延至 11/16（週一）
    q3 = statement_deadline(2026, 3)
    assert q3 == date(2026, 11, 16)
    assert q3.weekday() < 5


def test_q1_not_visible_in_april_but_visible_after_deadline() -> None:
    """回歸本題：Q1 財報在 4 月不可見、5/15 之後才可見。"""
    q1_deadline = statement_deadline(2026, 1)
    assert date(2026, 4, 20) < q1_deadline, "4 月讀得到 Q1 就是偷看未來"
    assert date(2026, 5, 15) >= q1_deadline, "過了法定期限就該看得到"

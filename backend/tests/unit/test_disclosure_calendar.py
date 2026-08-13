"""法定揭露期限單測(純函式,零 DB)。

每條測資都對應一個**已查證的法源或市場實務日期**,不是想像的情境。
法源:證交法 §36、公開發行公司財務報告及營運情形公告申報特殊適用範圍辦法 §3。
"""

from datetime import date

import pytest

from app.domain.disclosure_calendar import (
    FilerCategory,
    monthly_revenue_deadline,
    statement_deadline,
)


class TestQuarterlyGeneralRule:
    """證交法 §36:各該季終了後四十五日內。

    45 日推導出的日期與市場實務公告的期限**逐日吻合** —— 這是本規則正確的交叉佐證。
    """

    @pytest.mark.parametrize(
        ("year", "quarter", "expected"),
        [
            (2025, 1, date(2025, 5, 15)),  # 3/31 + 45
            (2025, 3, date(2025, 11, 14)),  # 9/30 + 45
            (2024, 1, date(2024, 5, 15)),
            (2024, 3, date(2024, 11, 14)),
        ],
    )
    def test_q1_q3_are_45_days_after_quarter_end(
        self, year: int, quarter: int, expected: date
    ) -> None:
        assert statement_deadline(year, quarter) == expected

    def test_q2_general_is_aug_14(self) -> None:
        """一般公司 Q2 = 6/30 + 45 = 8/14(市場實務證實)。"""
        assert statement_deadline(2025, 2) == date(2025, 8, 14)


class TestQ2FinancialException:
    """特殊適用範圍辦法 §3:金融保險業 / 第一上市(櫃)Q2 為終了後二個月。"""

    def test_financial_q2_is_aug_31_rolled_over_weekend(self) -> None:
        """2025-08-31 是**週日** → 順延至 9/1。

        這正是市場新聞報導的「金融保險、第一上市公司則延至 9／1」。
        """
        assert date(2025, 8, 31).weekday() == 6, "前提:2025-08-31 是週日"
        assert statement_deadline(2025, 2, category=FilerCategory.FINANCIAL) == date(2025, 9, 1)

    def test_financial_q2_no_rollover_when_weekday(self) -> None:
        """2024-08-31 是週六 → 順延至 9/2(週一)。"""
        assert statement_deadline(2024, 2, category=FilerCategory.FINANCIAL) == date(2024, 9, 2)

    def test_insurer_also_gets_q2_extension(self) -> None:
        assert statement_deadline(2025, 2, category=FilerCategory.INSURER) == date(2025, 9, 1)

    def test_financial_exception_only_applies_to_q2(self) -> None:
        """**只有 Q2 有 2 個月的例外**;Q1/Q3 金融業仍是 45 日。

        若誤把例外套到 Q1/Q3,會讓金融股的 Q1/Q3 晚 15 天才可見 —— 那是過度保守,
        雖不致偷看未來,但會平白丟掉資訊。
        """
        assert statement_deadline(2025, 1, category=FilerCategory.FINANCIAL) == date(2025, 5, 15)
        assert statement_deadline(2025, 3, category=FilerCategory.FINANCIAL) == date(2025, 11, 14)


class TestAnnualReport:
    def test_general_annual_is_mar_31_next_year(self) -> None:
        """證交法 §36:年度終了後三個月 → 次年 3/31(曆月加法,非 90 日)。"""
        assert statement_deadline(2024, 4) == date(2025, 3, 31)

    def test_large_cap_annual_is_75_days(self) -> None:
        """特殊適用範圍辦法:資本額 ≥100 億 → 75 日。

        2024-12-31 + 75 = 2025-03-16(**週日**)→ 順延 3/17。
        這正是證交所公告的「113 年財報申報期限為 3/17」。
        """
        assert statement_deadline(2024, 4, is_large_cap=True) == date(2025, 3, 17)

    def test_large_cap_is_earlier_than_general(self) -> None:
        """大型股期限**更早** —— 用通則(3/31)涵蓋它是保守的,不會偷看未來。"""
        assert statement_deadline(2024, 4, is_large_cap=True) < statement_deadline(2024, 4)


class TestMonthlyRevenue:
    def test_general_is_10th_of_next_month(self) -> None:
        """證交法 §36:每月十日以前公告上月份。"""
        assert monthly_revenue_deadline(2025, 1) == date(2025, 2, 10)

    def test_december_rolls_to_next_year(self) -> None:
        assert monthly_revenue_deadline(2025, 12) == date(2026, 1, 12)  # 1/10 週六 → 1/12

    def test_weekend_rollover(self) -> None:
        """2025-05-10 是週六 → 順延至 5/12(週一)。"""
        assert date(2025, 5, 10).weekday() == 5, "前提:2025-05-10 是週六"
        assert monthly_revenue_deadline(2025, 4) == date(2025, 5, 12)

    def test_insurer_extension_applies_from_2026(self) -> None:
        """保險業自 **115 會計年度(2026)起**才可延至 15 日。"""
        assert monthly_revenue_deadline(2026, 1, category=FilerCategory.INSURER) == date(
            2026, 2, 16
        )  # 2/15 週日 → 2/16

    def test_insurer_before_2026_still_10th(self) -> None:
        """**生效年度是硬邊界** —— 2025 年的保險業仍是 10 日。

        套錯會讓 2025 年以前的保險業月營收晚 5 天才可見(過度保守),
        反向套錯(把 15 日用到 2025)則會偷看未來。
        """
        assert monthly_revenue_deadline(2025, 1, category=FilerCategory.INSURER) == date(
            2025, 2, 10
        )

    def test_general_never_gets_extension(self) -> None:
        assert monthly_revenue_deadline(2026, 1) == date(2026, 2, 10)


class TestPitSafety:
    """本模組存在的理由:期限必須**晚於**期間結束,否則就是偷看未來。"""

    @pytest.mark.parametrize("quarter", [1, 2, 3, 4])
    @pytest.mark.parametrize("category", list(FilerCategory))
    def test_deadline_is_always_after_period_end(
        self, quarter: int, category: FilerCategory
    ) -> None:
        q_end = {
            1: date(2025, 3, 31),
            2: date(2025, 6, 30),
            3: date(2025, 9, 30),
            4: date(2025, 12, 31),
        }[quarter]
        assert statement_deadline(2025, quarter, category=category) > q_end

    def test_revenue_deadline_is_always_after_revenue_month(self) -> None:
        for m in range(1, 13):
            d = monthly_revenue_deadline(2025, m)
            assert (d.year, d.month) > (2025, m), f"{m} 月營收的期限不得落在該月內"

    def test_deadline_never_falls_on_weekend(self) -> None:
        """週末順延必須生效 —— 期限落在休市日等於那天沒人看得到。"""
        for q in (1, 2, 3, 4):
            for y in range(2015, 2027):
                assert statement_deadline(y, q).weekday() < 5


class TestInputValidation:
    def test_bad_quarter_fails_loud(self) -> None:
        with pytest.raises(ValueError, match="fiscal_quarter"):
            statement_deadline(2025, 5)

    def test_bad_month_fails_loud(self) -> None:
        with pytest.raises(ValueError, match="revenue_month"):
            monthly_revenue_deadline(2025, 13)

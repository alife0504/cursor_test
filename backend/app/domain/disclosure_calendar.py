"""台股法定資訊揭露期限(純函式,零 IO)。

## 為什麼需要這個模組

`financial_statements` 與 `monthly_revenue` 的 `announced_at` 實測 **100% 為 NULL**
(296,913 / 431,069 列全空)。沒有公告日就沒有 **PIT(point-in-time)正確性**:
Q1 的期間截止是 3/31,但實際 5/15 才公告 —— 任何 4 月的分析若讀得到 Q1 財報,
就是在**偷看未來**。這與存活者偏誤同類:不會報錯,只會讓回測系統性高估。

而上游(FinMind)**根本不給財報公告日**:
- `taiwan_stock_financial_statements` / `balance_sheet` / `cash_flows_statement`
  的欄位只有 `date, origin_name, stock_id, type, value` —— `date` 是**期間日**
- `taiwan_stock_month_revenue.date` 是**次月 1 日的慣例**,不是公告日
  (法定是次月 10 日前 → 拿它當公告日會偷看未來 9 天)
- `taiwan_stock_month_revenue.create_time` 只有 11.3% 有值,且其中 80%(45,285 列)
  是同一個值 `2026-05-19` —— 那是**批次回填的時間戳**,不是公告日
- 唯一有真公告日的是 `taiwan_stock_dividend.AnnouncementDate`(除權息,非財報)

故本模組推算**法定期限**作為保守的 PIT 邊界。

## 「期限」不是「公告日」—— 這個區別是本模組的全部重點

本模組算出來的是「**最晚一定會公開**」的日期,**不是**公司實際公告的日期。
公司可以提早公告(常見),但**法律上不能晚於**此日。故:

- 用它當 PIT 邊界 → **永遠不會偷看未來**(correct by construction)
- 代價 → 低估你實際能多早知道(某公司 5/1 就公告,我們假裝 5/15 才知道)

**保守會少賺,樂觀會爆炸。** 回測平台只能選前者。

真實公告日需接 **MOPS 公開資訊觀測站**;屆時 `announced_at` 填真值,
PIT 查詢用 `COALESCE(announced_at, disclosure_deadline)` 即自動升級。
**絕不可把本模組的輸出寫進 `announced_at`** —— 那會造出一個會說謊的欄位。

## 法源(2026-07-16 查證)

**通則 —— 證券交易法 §36**:
- 年度財務報告:每會計年度終了後**三個月內** → 12/31 + 3 個月 = **3/31**
- 第一/二/三季:各該季終了後**四十五日內**
  → Q1 3/31+45=**5/15** / Q2 6/30+45=**8/14** / Q3 9/30+45=**11/14**
- 每月營運情形:**每月十日以前**公告上月份

**例外 —— 公開發行公司財務報告及營運情形公告申報特殊適用範圍辦法 §3**:
- 實收資本額達 100 億以上之上市(櫃)公司:年報不得逾會計年度終了後 **75 日**
- 第一上市(櫃)公司(110 會計年度起)、金融保險業:Q2 不得逾第二季終了後 **2 個月**
  = **8/31**
- 保險業及具保險業子公司(115 會計年度起):月營收得延長至每月 **15 日**

45 日推導出的 5/15 / 8/14 / 11/14 與市場實務公告的期限**逐日吻合**,可交叉佐證。
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum

#: 證交法 §36:季報為各該季終了後「四十五日內」
QUARTERLY_DAYS: int = 45
#: 特殊適用範圍辦法 §3:資本額 ≥100 億者,年報「七十五日」內
LARGE_CAP_ANNUAL_DAYS: int = 75
#: 證交法 §36:月營收「每月十日以前」
MONTHLY_REVENUE_DAY: int = 10
#: 特殊適用範圍辦法 §3:保險業(115 會計年度起)得延至每月 15 日
INSURER_MONTHLY_REVENUE_DAY: int = 15
#: 保險業月營收延長的生效會計年度(民國 115 年 = 西元 2026)
INSURER_EXTENSION_FROM_YEAR: int = 2026


class FilerCategory(StrEnum):
    """申報人類別 —— 決定適用哪組期限。

    值域刻意最小化:只放**會改變期限**的區分,不做通用產業分類。
    """

    #: 一般公開發行公司(證交法 §36 通則)
    GENERAL = "general"
    #: 金融保險業 / 第一上市(櫃)—— Q2 延長至 2 個月(8/31)
    FINANCIAL = "financial"
    #: 保險業 —— 除 Q2 延長外,月營收自 115 會計年度起可延至 15 日
    INSURER = "insurer"


def _quarter_end(fiscal_year: int, fiscal_quarter: int) -> date:
    """會計季終了日。第四季 = 會計年度終了(12/31)。"""
    if fiscal_quarter not in (1, 2, 3, 4):
        raise ValueError(f"fiscal_quarter 必須是 1~4,收到 {fiscal_quarter}")
    return {
        1: date(fiscal_year, 3, 31),
        2: date(fiscal_year, 6, 30),
        3: date(fiscal_year, 9, 30),
        4: date(fiscal_year, 12, 31),
    }[fiscal_quarter]


def _roll_forward_weekend(d: date) -> date:
    """遇週末順延至下一個平日。

    **只處理週末,不處理國定假日**(本層無日曆相依,保持純函式)。
    影響:若期限落在國定假日,實際會再順延 1~2 天,而本函式會回較早的日期
    —— 即**最多樂觀 1~2 天**。已知限制,記於模組 docstring 與資料字典。
    真要精確需接交易日曆(dim_calendar),屬 P17 範疇。

    順延方向是**往後**,故對 PIT 而言是更保守(更晚才假裝知道),安全。
    """
    while d.weekday() >= 5:  # 5=六 6=日
        d += timedelta(days=1)
    return d


def statement_deadline(
    fiscal_year: int,
    fiscal_quarter: int,
    *,
    category: FilerCategory = FilerCategory.GENERAL,
    is_large_cap: bool = False,
) -> date:
    """財報的**法定最晚公告申報期限**(不是實際公告日)。

    :param fiscal_year: 會計年度(西元)
    :param fiscal_quarter: 1~4;**4 = 年度財務報告**(非「第四季季報」——
        台灣不單獨申報 Q4 季報,第四季的數字包含在年報中)
    :param category: 申報人類別(決定 Q2 是 45 日還是 2 個月)
    :param is_large_cap: 實收資本額是否達 100 億(僅影響年報:75 日 vs 3 個月)

    :return: 該期財報最晚必須公開的日期(遇週末已順延)

    實測對照(推導 vs 市場實務):
        Q1 2025 → 2025-05-15   Q2 2025(一般)→ 2025-08-14
        Q3 2025 → 2025-11-14   年報 2024 → 2025-03-31
        Q2 2025(金融保險)→ 2025-08-31(週日)→ 順延 2025-09-01
    """
    end = _quarter_end(fiscal_year, fiscal_quarter)

    if fiscal_quarter == 4:
        # 年報。通則:終了後三個月(曆月加法,非 90 日)→ 次年 3/31
        if is_large_cap:
            # 特殊適用範圍辦法:75 日。2024-12-31 + 75 = 2025-03-16(週日)→ 3/17
            raw = end + timedelta(days=LARGE_CAP_ANNUAL_DAYS)
        else:
            raw = date(fiscal_year + 1, 3, 31)
        return _roll_forward_weekend(raw)

    if fiscal_quarter == 2 and category in (FilerCategory.FINANCIAL, FilerCategory.INSURER):
        # 金融保險 / 第一上市:第二季終了後「二個月」→ 8/31
        raw = date(fiscal_year, 8, 31)
        return _roll_forward_weekend(raw)

    # 通則:各季終了後 45 日
    return _roll_forward_weekend(end + timedelta(days=QUARTERLY_DAYS))


def monthly_revenue_deadline(
    revenue_year: int,
    revenue_month: int,
    *,
    category: FilerCategory = FilerCategory.GENERAL,
) -> date:
    """月營收的**法定最晚公告申報期限**(不是實際公告日)。

    證交法 §36:每月十日以前公告上月份營運情形。
    保險業及具保險業子公司自 **115 會計年度(2026)起**得延至每月 15 日
    —— **注意生效年度**:2025 年以前的保險業仍是 10 日,套錯會偷看未來 5 天。

    :param revenue_year: 營收所屬年(**不是公告年**)
    :param revenue_month: 營收所屬月 1~12
    """
    if revenue_month not in range(1, 13):
        raise ValueError(f"revenue_month 必須是 1~12,收到 {revenue_month}")

    y, m = (revenue_year + 1, 1) if revenue_month == 12 else (revenue_year, revenue_month + 1)

    day = MONTHLY_REVENUE_DAY
    if category is FilerCategory.INSURER and revenue_year >= INSURER_EXTENSION_FROM_YEAR:
        day = INSURER_MONTHLY_REVENUE_DAY

    return _roll_forward_weekend(date(y, m, day))

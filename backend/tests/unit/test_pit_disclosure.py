"""PIT（point-in-time）正確性：財報/月營收不可在法定公開前被看到。

為什麼要有這組測試：
    財報期末 ≠ 可得日。Q1 期末 3/31，但法定 5/15 才須公告；若 4 月的分析讀得到 Q1 數字
    ＝**偷看未來**，回測系統性高估。這類錯誤**不會報錯**（與存活者偏誤、CF 累計基準同類）。

本檔測的是**本專案的寫入/讀取路徑**（repo helper、分類器），不是 disclosure_calendar
本身——那有自己的測試檔。先前版本只斷言 helper == domain 函式，等於在測別人的模組：
把整個寫入路徑與 PIT 過濾挖空，測試仍全綠（突變驗證證實）。故本檔一律針對
「拿掉實作就會紅」的行為下斷言。

方向不對稱（本檔的核心）：
    期限算得比法定**晚** → 保守，安全
    期限算得比法定**早** → 偷看未來，危險
    故未知類別時必須取期限最晚者。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.disclosure_calendar import FilerCategory, statement_deadline
from app.domain.filer_classification import filer_category_for
from app.domain.instrument_classification import is_tw_warrant
from app.repos.financials_repo import (
    _safe_monthly_revenue_deadline,
    _safe_statement_deadline,
)

pytestmark = pytest.mark.unit


# ── 分類器：產業別 → 申報人類別 ──────────────────────────


@pytest.mark.parametrize(
    "industry",
    ["金融保險", "金融保險業", "銀行業", "保險業", "證券業"],
)
def test_financial_industries_map_to_insurer(industry: str) -> None:
    """金融保險類必須落在期限較晚的類別，否則 Q2 會早 18 天開放。"""
    assert filer_category_for(industry) is FilerCategory.INSURER


@pytest.mark.parametrize("industry", ["水泥工業", "電子工業", "半導體業", "航運業", "ETF"])
def test_general_industries_map_to_general(industry: str) -> None:
    assert filer_category_for(industry) is FilerCategory.GENERAL


@pytest.mark.parametrize(
    "name",
    ["鮮活果汁-KY", "美食-KY", "IKKA-KY", "慧洋-KY", "亞德客-KY"],
)
def test_first_listed_ky_maps_to_financial_not_general(name: str) -> None:
    """第一上市(櫃)/KY 股（-KY 後綴）Q2 法定期限為 2 個月(8/31)，非一般 8/14。

    KY 股全非金融產業（industry 落一般類），若只看 industry 會判 GENERAL → Q2 期限寫成
    8/14 → 每年 Q2 偷看未來 17 天。修正後以股名 -KY 後綴判為 FINANCIAL（Q2 8/31，但月營收
    仍 10 日，KY 非保險業）。此測試拿掉 KY 偵測就會紅。
    """
    # 產業別是一般類（食品/汽車/電機…），只有股名能識別 KY
    cat = filer_category_for("食品工業", name)
    assert cat is FilerCategory.FINANCIAL
    # 且確實把 Q2 期限推到 8/31（比 GENERAL 的 8/14 晚 → 不偷看未來）
    assert statement_deadline(2025, 2, category=cat) > statement_deadline(
        2025, 2, category=FilerCategory.GENERAL
    )
    # 但月營收維持 10 日（非保險業，不吃 15 日延長）
    from app.domain.disclosure_calendar import monthly_revenue_deadline

    assert monthly_revenue_deadline(2026, 3, category=cat) == monthly_revenue_deadline(
        2026, 3, category=FilerCategory.GENERAL
    )


def test_financial_ky_stays_insurer_most_conservative() -> None:
    """金融關鍵字優先於 KY：金融 KY 仍取最保守 INSURER（涵蓋 KY 的 8/31 且月營收 15 日）。"""
    assert filer_category_for("金融保險", "某金控-KY") is FilerCategory.INSURER


@pytest.mark.parametrize("industry", [None, ""])
def test_unknown_industry_falls_back_to_the_LATER_deadline(industry: str | None) -> None:
    """未知產業別 → INSURER 而非 GENERAL。

    這是刻意的方向選擇：猜 GENERAL 若猜錯（其實是金融股）就會偷看未來 18 天；
    猜 INSURER 若猜錯只是晚 17 天才看到。保守會少賺，樂觀會爆炸。
    """
    assert filer_category_for(industry) is FilerCategory.INSURER
    # 並且該預設確實產生較晚的期限（否則此選擇沒有意義）
    assert statement_deadline(2025, 2, category=FilerCategory.INSURER) > statement_deadline(
        2025, 2, category=FilerCategory.GENERAL
    )


# ── repo 寫入路徑：預設必須是保守的那一邊 ────────────────


def test_statement_deadline_helper_defaults_to_conservative_category() -> None:
    """不傳 category 時必須等同 INSURER（8/31），**不可**等同 GENERAL（8/14）。

    這正是本次審查揪出的 CRITICAL：helper 原本沒傳 category → 吃 GENERAL 預設 →
    金融股 Q2 期限被寫成 8/14，比法定 9/1 早 18 天 → PIT 邊界提早開放。
    """
    got = _safe_statement_deadline(2025, 2)
    assert got == statement_deadline(2025, 2, category=FilerCategory.INSURER)
    assert got != statement_deadline(2025, 2, category=FilerCategory.GENERAL)


def test_statement_deadline_helper_honours_explicit_category() -> None:
    """一般公司 Q2 = 8/14；金融保險 Q2 = 8/31（2025 適逢週日 → 順延 9/1）。"""
    assert _safe_statement_deadline(2025, 2, FilerCategory.GENERAL) == date(2025, 8, 14)
    assert _safe_statement_deadline(2025, 2, FilerCategory.INSURER) == date(2025, 9, 1)


def test_monthly_revenue_helper_defaults_to_conservative_category() -> None:
    """月營收預設亦須取較晚者：保險業自 2026 起 15 日，一般 10 日。"""
    got = _safe_monthly_revenue_deadline(2026, 1)
    assert got == date(2026, 2, 16)  # 2/15 為週日 → 順延 2/16
    assert got > _safe_monthly_revenue_deadline(2026, 1, FilerCategory.GENERAL)


@pytest.mark.parametrize("bad_quarter", [0, 5, -1, 99])
def test_bad_quarter_returns_none_not_crash(bad_quarter: int) -> None:
    """資料異常不該讓整批 upsert 掛掉——回 None（該列就不會被 PIT 查詢看到）。"""
    assert _safe_statement_deadline(2026, bad_quarter) is None


@pytest.mark.parametrize("bad_month", [0, 13, -1])
def test_bad_month_returns_none_not_crash(bad_month: int) -> None:
    assert _safe_monthly_revenue_deadline(2026, bad_month) is None


# ── 核心不變式：期限絕不可早於期末 ───────────────────────


_PERIOD_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


@pytest.mark.parametrize("category", [FilerCategory.GENERAL, FilerCategory.INSURER])
@pytest.mark.parametrize("fiscal_year", [2020, 2025, 2026])
@pytest.mark.parametrize("fiscal_quarter", [1, 2, 3, 4])
def test_deadline_never_earlier_than_period_end(
    fiscal_year: int, fiscal_quarter: int, category: FilerCategory
) -> None:
    """資料要到期末才存在，期限必定 >= 期末；早於期末 = PIT 邊界比事實早開放。"""
    month, day = _PERIOD_END[fiscal_quarter]
    assert _safe_statement_deadline(fiscal_year, fiscal_quarter, category) >= date(
        fiscal_year, month, day
    )


def test_q1_hidden_in_april_visible_after_deadline() -> None:
    """回歸本題：Q1 財報 4 月不可見、5/15 起可見（用 helper 實際算，非重述常數）。"""
    q1 = _safe_statement_deadline(2026, 1, FilerCategory.GENERAL)
    assert date(2026, 4, 20) < q1, "4 月讀得到 Q1 就是偷看未來"
    assert date(2026, 5, 15) >= q1, "過了法定期限就該看得到"


# ── 權證分類器（代號區間，不看名稱）─────────────────────


@pytest.mark.parametrize(
    "symbol",
    ["030793", "03726B", "03012X", "040001", "059999", "060001", "080001", "700001", "739999"],
)
def test_warrant_prefixes_detected(symbol: str) -> None:
    """上市 03~08、上櫃 70~73 的 6 碼代號皆為權證（含牛證/熊證）。"""
    assert is_tw_warrant(symbol) is True


@pytest.mark.parametrize(
    ("symbol", "why"),
    [
        ("2330", "台積電"),
        ("2945", "三商家購——真公司，名稱含『購』"),
        ("3085", "新零售——真公司，名稱含『售』"),
        ("0050", "ETF"),
        ("00400A", "主動式 ETF"),
        ("006201", "ETF"),
        ("01001T", "REIT"),
        ("020000", "ETN"),
        ("910322", "存託憑證 DR"),
        ("2887Z1", "特別股"),
        (None, "None"),
        ("", "空字串"),
    ],
)
def test_non_warrants_not_misclassified(symbol: str | None, why: str) -> None:
    """反向護欄：真公司/ETF/REIT/ETN/DR/特別股 一律不可被判為權證。

    先前用「名稱含購/售」的規則會誤判 2945 三商家購、3085 新零售，
    只靠 6 碼長度這個巧合才沒出事；改用代號區間後不再依賴名稱。
    """
    assert is_tw_warrant(symbol) is False, why

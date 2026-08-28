"""產業別 → 申報人類別（FilerCategory）分類。

為什麼要獨立一層：
    財報法定期限**依申報人類別而異**（見 app.domain.disclosure_calendar）：
      - 一般公司 Q2 → 各季終了後 45 日 = 8/14
      - 金融保險 Q2 → 終了後二個月     = 8/31
      - 保險業月營收 → 自 115 會計年度(2026)起得延至 15 日（一般為 10 日）
    寫入 disclosure_deadline 時若不分類別、一律套 GENERAL，會對金融股寫入**過早**的期限
    → PIT 邊界提早開放 → 每年 Q2 有 18 天偷看未來（8/14~9/1）。全體金控/保險股中招。

**錯誤方向不對稱 —— 這是本模組的核心**：
    期限算得比法定**晚** → 資料晚點才看得到（保守，安全）
    期限算得比法定**早** → 宣稱「你那時就知道了」，但法律上還沒公開 → 偷看未來（危險）
    故**分類不確定時一律取期限最晚的類別**（INSURER）。保守會少賺，樂觀會爆炸。

分類依據：stock_list.industry，來源為 FinMind 的 industry_category
（scripts/backfill_industry.py 從本地庫回填；實測 active 台股 2,401 檔中 2,374 檔有值）。
FinMind 的「金融保險」把銀行、保險、金控混為一類，無法細分 → 一律取 INSURER
（Q2 8/31 且月營收 15 日，兩者都是該群中最晚者），對純銀行只是多等 5 天，安全。
"""

from __future__ import annotations

from app.domain.disclosure_calendar import FilerCategory

#: FinMind industry_category 中屬於金融保險的關鍵字
_FINANCIAL_KEYWORDS: tuple[str, ...] = ("金融", "保險", "銀行", "證券")


def _is_first_listed_ky(name: str | None) -> bool:
    """是否為第一上市(櫃)/KY 股（以股名後綴「-KY」判定）。

    台股外國企業來台第一上市(櫃)者股名一律帶「-KY」後綴（如「鮮活果汁-KY」「美食-KY」），
    實測台股 120 檔 KY 全數如此、且全非金融產業。此為可靠且完整涵蓋 KY 群的識別。
    （非 KY 的其他第一上市型態極少，且無可靠資料源；見模組層 flag，屬 needs_human 殘留。）
    """
    return bool(name) and name.strip().upper().endswith("-KY")


def filer_category_for(industry: str | None, name: str | None = None) -> FilerCategory:
    """由產業別（+股名）推申報人類別。

    :param industry: stock_list.industry（FinMind industry_category），可為 None
    :param name: stock_list.name —— 用於識別第一上市(櫃)/KY 股（-KY 後綴）
    :return: 期限適用的 FilerCategory

    分類優先序（皆為「錯就錯在安全方向」）：
    1. 金融保險關鍵字 → INSURER（Q2 8/31 + 月營收 15 日，該群最保守）。
    2. 第一上市(櫃)/KY → FINANCIAL：Q2 法定期限為終了後 2 個月(8/31) 而非一般 8/14，
       否則每年 Q2 有 17 天 look-ahead（KY 非保險業，月營收仍為 10 日，故用 FINANCIAL 非 INSURER）。
    3. industry 為 None/空 → INSURER（未知取最晚者，不偷看未來）。
    4. 其餘 → GENERAL。
    """
    if industry and any(k in industry for k in _FINANCIAL_KEYWORDS):
        return FilerCategory.INSURER
    if _is_first_listed_ky(name):
        return FilerCategory.FINANCIAL
    if not industry:
        return FilerCategory.INSURER
    return FilerCategory.GENERAL


#: 給 SQL 用的等價運算式（回填腳本要在 DB 端分類，不能逐列拉回 Python）。
#: 必須與 filer_category_for 保持同義——金融關鍵字→insurer、KY→financial、NULL→insurer、其餘→general。
#: 順序需與 Python 一致（關鍵字優先於 KY，避免金融 KY 被降成 financial 而非最保守的 insurer）。
SQL_FILER_CATEGORY_EXPR = (
    "CASE WHEN s.industry ~ '金融|保險|銀行|證券' THEN 'insurer' "
    "WHEN upper(s.name) LIKE '%-KY' THEN 'financial' "
    "WHEN s.industry IS NULL OR s.industry = '' THEN 'insurer' "
    "ELSE 'general' END"
)


__all__ = ["SQL_FILER_CATEGORY_EXPR", "filer_category_for"]

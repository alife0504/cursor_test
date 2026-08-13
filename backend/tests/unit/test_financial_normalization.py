"""財報正規化 / pivot / 現金流還原單元測試。

重點守住「會計基準」這件事：FinMind 的損益表是「單季」，但現金流量表是「年度累計(YTD)」
（台灣申報慣例）。若不還原就把兩者塞進同一個 fiscal_quarter，Q2~Q4 的現金流會含前幾季，
與同季的單季營收並列 → 下游比率全錯。

測試中的數字取自本地 FinMind 庫的真實值（2330 FY2024），故此檔同時也是該行為的文件：
- 損益表 Revenue：592,644,201,000 / 673,510,177,000 / 759,692,143,000 / 868,461,178,000
  （四季加總 2,894,307,699,000 = 台積電公告全年營收 → 單季基準）
- 現金流 營業活動：436,311,108,000 / 813,979,318,000 / 1,205,971,785,000 / 1,826,177,068,000
  （單調遞增、Q4 = 公告全年數 → YTD 累計基準）
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.services.data_pipeline_service import DataPipelineService

pytestmark = pytest.mark.unit


def _item(d: str, typ: str, value: Any, statement_type: str | None = None) -> dict[str, Any]:
    it: dict[str, Any] = {
        "symbol": "2330",
        "date": d,
        "date_parsed": date.fromisoformat(d),
        "type": typ,
        "value": Decimal(str(value)),
        "origin_name": typ,
    }
    if statement_type is not None:
        it["statement_type"] = statement_type
    return it


def _norm(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return DataPipelineService._normalize_financial_rows("2330", items, source="finmind_local")


def _row(rows: list[dict[str, Any]], st: str, q: int, yr: int = 2024) -> dict[str, Any]:
    for r in rows:
        if r["statement_type"] == st and r["fiscal_quarter"] == q and r["fiscal_year"] == yr:
            return r
    raise AssertionError(f"找不到 {st} {yr}Q{q}")


# ── 損益表：單季基準，原值直接進 typed 欄位 ──────────────


def test_income_statement_pivots_to_typed_columns() -> None:
    rows = _norm(
        [
            _item("2024-03-31", "Revenue", 592644201000, "IS"),
            _item("2024-03-31", "GrossProfit", 314000000000, "IS"),
            _item("2024-03-31", "OperatingIncome", 249000000000, "IS"),
            _item("2024-03-31", "IncomeAfterTaxes", 225490000000, "IS"),
            _item("2024-03-31", "EPS", 8.70, "IS"),
        ]
    )
    r = _row(rows, "IS", 1)
    assert r["revenue"] == Decimal("592644201000")
    assert r["gross_profit"] == Decimal("314000000000")
    assert r["operating_income"] == Decimal("249000000000")
    assert r["net_income"] == Decimal("225490000000")
    assert r["eps"] == Decimal("8.70")


def test_income_statement_is_not_decumulated() -> None:
    """損益表本來就是單季，絕不可被減去前一季。"""
    rows = _norm(
        [
            _item("2024-03-31", "Revenue", 592644201000, "IS"),
            _item("2024-06-30", "Revenue", 673510177000, "IS"),
        ]
    )
    assert _row(rows, "IS", 1)["revenue"] == Decimal("592644201000")
    assert _row(rows, "IS", 2)["revenue"] == Decimal("673510177000")  # 原值，未被相減


def test_untagged_items_default_to_income_statement() -> None:
    """FinMind API 損益源不帶 statement_type → 應預設當 IS 處理。"""
    rows = _norm([_item("2024-03-31", "Revenue", 592644201000)])
    assert len(rows) == 1
    assert rows[0]["statement_type"] == "IS"
    assert rows[0]["revenue"] == Decimal("592644201000")


# ── 資產負債表：時點快照，不還原 ─────────────────────────


def test_balance_sheet_is_point_in_time_not_decumulated() -> None:
    """資產負債表是時點餘額，Q2 不可減 Q1。"""
    rows = _norm(
        [
            _item("2024-03-31", "TotalAssets", 5000, "BS"),
            _item("2024-03-31", "Liabilities", 2000, "BS"),
            _item("2024-03-31", "Equity", 3000, "BS"),
            _item("2024-06-30", "TotalAssets", 5500, "BS"),
            _item("2024-06-30", "Liabilities", 2200, "BS"),
            _item("2024-06-30", "Equity", 3300, "BS"),
        ]
    )
    q2 = _row(rows, "BS", 2)
    assert q2["total_assets"] == Decimal("5500")  # 不是 500
    assert q2["total_liabilities"] == Decimal("2200")
    assert q2["total_equity"] == Decimal("3300")
    # 會計恒等式仍成立
    assert q2["total_assets"] == q2["total_liabilities"] + q2["total_equity"]


# ── 現金流量表：YTD 累計 → 還原成單季 ────────────────────


def _cf_year_2330_2024() -> list[dict[str, Any]]:
    """2330 FY2024 營業活動現金流真實 YTD 值。"""
    return [
        _item("2024-03-31", "CashFlowsFromOperatingActivities", 436311108000, "CF"),
        _item("2024-06-30", "CashFlowsFromOperatingActivities", 813979318000, "CF"),
        _item("2024-09-30", "CashFlowsFromOperatingActivities", 1205971785000, "CF"),
        _item("2024-12-31", "CashFlowsFromOperatingActivities", 1826177068000, "CF"),
    ]


def test_cashflow_ytd_is_decumulated_into_standalone_quarters() -> None:
    """核心迴歸：YTD 應還原成單季，且四季加總 = 原 Q4 的全年數。"""
    rows = _norm(_cf_year_2330_2024())
    q1 = _row(rows, "CF", 1)["operating_cashflow"]
    q2 = _row(rows, "CF", 2)["operating_cashflow"]
    q3 = _row(rows, "CF", 3)["operating_cashflow"]
    q4 = _row(rows, "CF", 4)["operating_cashflow"]

    assert q1 == Decimal("436311108000")  # Q1 的 YTD 即單季
    assert q2 == Decimal("813979318000") - Decimal("436311108000")
    assert q3 == Decimal("1205971785000") - Decimal("813979318000")
    assert q4 == Decimal("1826177068000") - Decimal("1205971785000")

    # 還原後四季加總必須等於原本 Q4 的 YTD（= 公告全年營業現金流）
    assert q1 + q2 + q3 + q4 == Decimal("1826177068000")


def test_decumulation_does_not_bleed_across_years() -> None:
    """跨年度不可相減：新年度 Q1 的 YTD 就是單季，不能去減前一年 Q4。"""
    items = [
        *_cf_year_2330_2024(),
        _item("2025-03-31", "CashFlowsFromOperatingActivities", 500000000000, "CF"),
    ]
    rows = _norm(items)
    assert _row(rows, "CF", 1, yr=2025)["operating_cashflow"] == Decimal("500000000000")


def test_decumulation_without_prior_quarter_yields_none_not_wrong_number() -> None:
    """缺前一季時無法還原 → 應為 None（標示不知道），而不是留下 YTD 這個錯數字。"""
    rows = _norm([_item("2024-09-30", "CashFlowsFromOperatingActivities", 1205971785000, "CF")])
    assert _row(rows, "CF", 3)["operating_cashflow"] is None


def test_cashflow_all_three_columns_decumulated_including_negatives() -> None:
    """投資/籌資現金流多為負值，還原邏輯同樣要正確。"""
    rows = _norm(
        [
            _item("2024-03-31", "CashProvidedByInvestingActivities", -100, "CF"),
            _item("2024-06-30", "CashProvidedByInvestingActivities", -250, "CF"),
            _item("2024-03-31", "CashFlowsProvidedFromFinancingActivities", -30, "CF"),
            _item("2024-06-30", "CashFlowsProvidedFromFinancingActivities", -80, "CF"),
        ]
    )
    assert _row(rows, "CF", 2)["investing_cashflow"] == Decimal("-150")  # -250 - (-100)
    assert _row(rows, "CF", 2)["financing_cashflow"] == Decimal("-50")  # -80 - (-30)


def test_cashflow_operating_synonym_is_mapped() -> None:
    """舊年度用 NetCashInflowFromOperatingActivities（本地庫 35,706 列）也要對映。"""
    rows = _norm(
        [
            _item("2011-03-31", "NetCashInflowFromOperatingActivities", 1000, "CF"),
            _item("2011-06-30", "NetCashInflowFromOperatingActivities", 2500, "CF"),
        ]
    )
    assert _row(rows, "CF", 1, yr=2011)["operating_cashflow"] == Decimal("1000")
    assert _row(rows, "CF", 2, yr=2011)["operating_cashflow"] == Decimal("1500")


# ── 三表混合：各自 statement_type 一列，互不污染 ──────────


def test_is_bs_cf_produce_separate_rows_per_quarter() -> None:
    rows = _norm(
        [
            _item("2024-03-31", "Revenue", 592644201000, "IS"),
            _item("2024-03-31", "TotalAssets", 5000, "BS"),
            _item("2024-03-31", "CashFlowsFromOperatingActivities", 436311108000, "CF"),
        ]
    )
    assert len(rows) == 3
    assert {r["statement_type"] for r in rows} == {"IS", "BS", "CF"}
    # IS 列不應被塞進 BS/CF 的欄位，反之亦然
    assert _row(rows, "IS", 1).get("total_assets") is None
    assert _row(rows, "BS", 1).get("revenue") is None
    assert _row(rows, "CF", 1).get("revenue") is None

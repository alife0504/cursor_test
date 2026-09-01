"""資料新鮮度閾值判定單元測試（純邏輯部分）。

compute_freshness 需 DB（整合層），但 _status 的 ok/warn/critical 判定是純函式，
且直接決定「網頁警示 banner 與 Prometheus alert 何時觸發」，必須鎖死不回歸。
"""

from __future__ import annotations

import pytest

from app.services.freshness_service import _SPECS, _status

pytestmark = pytest.mark.unit


def _spec(key: str):
    return next(s for s in _SPECS if s.key == key)


def test_status_none_is_unknown() -> None:
    assert _status(None, _spec("stock_prices")) == "unknown"


def test_daily_table_thresholds() -> None:
    sp = _spec("stock_prices")  # warn=4, crit=8
    assert _status(0, sp) == "ok"
    assert _status(4, sp) == "ok"
    assert _status(5, sp) == "warn"
    assert _status(8, sp) == "warn"
    assert _status(9, sp) == "critical"


def test_monthly_revenue_thresholds_absorb_inherent_lag() -> None:
    # 月頻資料天生落後 ~40-62 天仍屬健康，閾值須大於此以免誤報。
    mr = _spec("monthly_revenue")  # warn=75, crit=110
    assert _status(62, mr) == "ok"  # 已是最新可得月，健康
    assert _status(92, mr) == "warn"  # 缺上一個月
    assert _status(120, mr) == "critical"  # 缺兩個月以上


def test_index_has_dedicated_spec_not_masked_by_stocks() -> None:
    # 大盤指數獨立監控（原本被 2000+ 個股 max(date) 遮蔽）。
    idx = _spec("index")
    assert "TAIEX" in idx.sql
    assert _status(9, idx) == "critical"


def test_all_specs_have_sane_thresholds() -> None:
    for s in _SPECS:
        assert 0 < s.warn_days <= s.crit_days, f"{s.key} 閾值不合理"

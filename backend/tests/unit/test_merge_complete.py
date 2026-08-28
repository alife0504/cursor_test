"""_merge_complete 完成判定回歸測試。

背景：多源「按日合併涵蓋」用 _merge_complete 決定是否提早結束（省配額）。
交易日曆 trading_calendar 源自 bronze.taiwan_stock_price（與 finmind_local 同源），
故本地資料湖落後時日曆也落後。原實作在此情況只看 issubset → 提早結束、永遠問不到
比本地庫更新的資料（實測：本地/日曆到 08-27、finmind API 已有 08-28，整市場漏抓當日）。

本測試鎖死修正後的行為：日曆落後 end 時，除非 merged 自身也達到 end，否則不得判定完整。
"""

from __future__ import annotations

from datetime import date

from app.services.data_pipeline_service import _MERGE_MAX_GAP_DAYS, _merge_complete


def _d(*days: int) -> set[date]:
    return {date(2026, 8, d) for d in days}


def _merged(*days: int) -> dict:
    return {date(2026, 8, d): {"close": 1} for d in days}


class TestMergeCompleteCalendarLag:
    """交易日曆落後於 end 時的核心回歸（原缺陷所在）。"""

    def test_calendar_lags_and_merged_stops_at_calendar_horizon_is_incomplete(self) -> None:
        # 日曆與本地庫皆只到 08-27，但 end=08-28（今日、實為交易日）。
        # 原缺陷：issubset(expected⊆merged)=True → 提早結束、不問較新來源。
        # 修正後：日曆未達 end 且 merged 未達 end → 必須續問（回 False）。
        cal = _d(21, 22, 25, 26, 27)
        merged = _merged(21, 22, 25, 26, 27)
        assert _merge_complete(merged, date(2026, 8, 28), cal) is False

    def test_calendar_lags_but_fresher_source_reached_end_is_complete(self) -> None:
        # 續問 finmind API 後補上 08-28：日曆仍到 27，但 merged 已達 end → 可停。
        cal = _d(21, 22, 25, 26, 27)
        merged = _merged(21, 22, 25, 26, 27, 28)
        assert _merge_complete(merged, date(2026, 8, 28), cal) is True

    def test_calendar_lags_multiple_days_is_incomplete(self) -> None:
        cal = _d(21, 22, 25)
        merged = _merged(21, 22, 25)
        assert _merge_complete(merged, date(2026, 8, 28), cal) is False


class TestMergeCompleteCalendarCurrent:
    """交易日曆已延伸到 end：走精準判定分支。"""

    def test_calendar_reaches_end_all_covered_is_complete(self) -> None:
        cal = _d(21, 22, 25, 26, 27, 28)
        merged = _merged(21, 22, 25, 26, 27, 28)
        assert _merge_complete(merged, date(2026, 8, 28), cal) is True

    def test_calendar_reaches_end_missing_one_trading_day_is_incomplete(self) -> None:
        # 日曆說 08-28 是交易日，但 merged 缺它 → 續問（精準單日缺口偵測）。
        cal = _d(21, 22, 25, 26, 27, 28)
        merged = _merged(21, 22, 25, 26, 27)
        assert _merge_complete(merged, date(2026, 8, 28), cal) is False

    def test_calendar_excludes_holiday_not_flagged_missing(self) -> None:
        # 颱風/臨時休市不在日曆內：merged 沒有該日也算完整（不誤觸）。
        # 假設 08-26 停市（不在 cal），merged 也沒有 → 仍完整。
        cal = _d(21, 22, 25, 27, 28)
        merged = _merged(21, 22, 25, 27, 28)
        assert _merge_complete(merged, date(2026, 8, 28), cal) is True


class TestMergeCompleteHeuristicFallback:
    """無交易日曆（cal_days 為空/None）：退回啟發式。"""

    def test_no_calendar_reaches_end_no_gap_is_complete(self) -> None:
        merged = _merged(25, 26, 27, 28)
        assert _merge_complete(merged, date(2026, 8, 28), set()) is True
        assert _merge_complete(merged, date(2026, 8, 28), None) is True

    def test_no_calendar_not_reaching_end_is_incomplete(self) -> None:
        merged = _merged(25, 26, 27)
        assert _merge_complete(merged, date(2026, 8, 28), None) is False

    def test_no_calendar_big_internal_gap_is_incomplete(self) -> None:
        # 中間有 > 15 天大洞（整段缺漏）→ 不算完整。
        merged = {date(2026, 8, 1): {}, date(2026, 8, 28): {}}
        assert (date(2026, 8, 28) - date(2026, 8, 1)).days > _MERGE_MAX_GAP_DAYS
        assert _merge_complete(merged, date(2026, 8, 28), None) is False


def test_empty_merged_is_never_complete() -> None:
    assert _merge_complete({}, date(2026, 8, 28), _d(27, 28)) is False
    assert _merge_complete({}, date(2026, 8, 28), None) is False

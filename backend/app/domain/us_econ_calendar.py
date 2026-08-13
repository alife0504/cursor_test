"""美國重大經濟數據公布日（財報日曆用）。

無 FRED API key 時的離線來源：只放「能精確定日」的重大事件，避免給錯日期。
- FOMC 利率決議：Fed 官方公布的 2026 年會議日（決議日=會議第二天，14:00 ET）。
- 非農就業（Employment Situation / NFP）：每月第一個週五（08:30 ET）。鐵律。
- ISM 製造業 PMI：每月第一個營業日（10:00 ET）。鐵律。

台北時間：US 東部時間換算，含日光節約（EDT=UTC-4 於 3 月第二個週日～11 月第一個週日，
其餘 EST=UTC-5）。台北=UTC+8。
CPI / GDP / PCE / 零售等公布日不固定、需 BLS/BEA 排程表 → 待接 FRED release calendar API 後補。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# Fed 官方公布的 FOMC 決議日（會議第二天）。逐年維護；沒有的年份就不顯示（優雅缺席）。
_FOMC_DECISION_DAYS: dict[int, list[tuple[int, int]]] = {
    2026: [(1, 28), (3, 18), (4, 29), (6, 17), (7, 29), (9, 16), (10, 28), (12, 9)],
    2027: [(1, 27), (3, 17)],  # 跨年查詢用；完整 2027 待 Fed 公布後補
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """該月第 n 個某星期幾（weekday: 週一=0…週日=6）。"""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + (n - 1) * 7)


def _first_friday(year: int, month: int) -> date:
    return _nth_weekday(year, month, 4, 1)  # 週五=4


def _first_business_day(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() >= 5:  # 六=5、日=6
        d += timedelta(days=1)
    return d


def _is_us_dst(d: date) -> bool:
    """美國日光節約：3 月第二個週日 ~ 11 月第一個週日。"""
    start = _nth_weekday(d.year, 3, 6, 2)  # 3 月第二個週日
    end = _nth_weekday(d.year, 11, 6, 1)  # 11 月第一個週日
    return start <= d < end


def _taipei_time(d: date, et_hour: int, et_min: int) -> str:
    """把 US 東部時刻換算成台北 HH:MM（跨日不標日期，日曆已按 event_date 分格）。"""
    utc_offset = 4 if _is_us_dst(d) else 5  # ET = UTC - offset
    taipei = (et_hour + utc_offset + 8) % 24
    return f"{taipei:02d}:{et_min:02d}"


def _months_in_range(from_date: date, to_date: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = from_date.year, from_date.month
    while (y, m) <= (to_date.year, to_date.month):
        out.append((y, m))
        m = 1 if m == 12 else m + 1
        y = y + 1 if m == 1 else y
    return out


def us_econ_events(from_date: date, to_date: date) -> list[dict[str, Any]]:
    """回 [from,to] 區間內的美國重大數據事件（event_type='us_econ'）。"""
    out: list[dict[str, Any]] = []

    def _add(d: date, title: str, tp_time: str) -> None:
        if from_date <= d <= to_date:
            out.append(
                {
                    "symbol": None,
                    "name": "美國",
                    "market": "US",
                    "event_type": "us_econ",
                    "event_date": d.isoformat(),
                    "title": f"{title}（台北 {tp_time}）",
                    "source": "curated",
                }
            )

    for y, m in _months_in_range(from_date, to_date):
        nfp = _first_friday(y, m)
        _add(nfp, "美國非農就業", _taipei_time(nfp, 8, 30))
        ism = _first_business_day(y, m)
        _add(ism, "美國 ISM 製造業 PMI", _taipei_time(ism, 10, 0))
        for mm, dd in _FOMC_DECISION_DAYS.get(y, []):
            if mm == m:
                fomc = date(y, mm, dd)
                # FOMC 決議 14:00 ET → 台北多為隔日凌晨
                _add(fomc, "FOMC 利率決議", _taipei_time(fomc, 14, 0))

    out.sort(key=lambda e: e["event_date"])
    return out


__all__ = ["us_econ_events"]

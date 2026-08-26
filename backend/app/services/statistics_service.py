"""績效統計 — 真實命中率（signal vs 分析建立「之後」N 日實際報酬）。

PIT 原則（本專案第一原則）：
- 報酬視窗**完全在分析建立時間之後**：用 T 之後的價格「評分」T 當下的決策，
  屬「實現結果」而非偷看未來（偷看未來＝拿 T 之後的資料去「做」決策）。
- 視窗尚未過完（最新可得日 K < 目標出場日）→ 標記 pending，不硬湊。
- 進場價＝決策日 D0 前 `entry_tol` 天內最近的收盤；出場價＝D0+N 起 `exit_tol`
  天內第一根收盤。容差窗吸收假日／時區±1 天／資料缺口，避免抓到很遠的 bar 失真。
- 報酬用 `COALESCE(adjusted_close, close)`：有還原價時＝含息總報酬；否則退回原始收盤
  （價格報酬，除息跳空會計入）。**現況：美股 yfinance 已提供 adjusted_close；台股尚未
  回填還原價，故台股標的目前為未還原收盤——除息旺季 BUY 命中率可能略被低估。台股還原
  權值回填為後續強化項（見稽核）。** 進出場同取自現時表→基準一致，PIT 安全。

命中定義：BUY → 報酬 > 0 視為命中；SELL → 報酬 < 0 視為命中（HOLD 無方向，排除）。
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisReport
from app.models.price import StockPrice

RowStatus = Literal["scored", "pending", "no_data"]

# 一次最多納入計算的分析筆數（保護計算量）
_MAX_ANALYSES = 1000


def _pick_entry(dates: list[date_type], d0: date_type, entry_tol_days: int) -> int | None:
    """回傳 D0 前 entry_tol 天內「最近」收盤的索引；無則 None。"""
    # 最右一個 date <= d0
    hi = bisect_right(dates, d0) - 1
    if hi < 0:
        return None
    if dates[hi] < d0 - timedelta(days=entry_tol_days):
        return None
    return hi


def _pick_exit(
    dates: list[date_type],
    target: date_type,
    exit_tol_days: int,
    latest: date_type,
) -> tuple[int | None, RowStatus]:
    """回傳 target 起 exit_tol 天內「第一根」收盤的索引 + 狀態。

    - 找到 → (idx, "scored")
    - 最新可得日 < target（視窗未過完 / 資料未進） → (None, "pending")
    - 有更後面的資料但容差窗內無 bar（資料缺口） → (None, "no_data")
    """
    if latest < target:
        return None, "pending"
    # 第一個 date >= target
    lo = bisect_left(dates, target)
    if lo >= len(dates):
        return None, "pending"
    if dates[lo] > target + timedelta(days=exit_tol_days):
        return None, "no_data"
    return lo, "scored"


def score_analyses(
    analyses: list[dict[str, Any]],
    prices_by_symbol: dict[str, list[tuple[date_type, Decimal]]],
    *,
    horizon_days: int,
    entry_tol_days: int = 14,
    exit_tol_days: int = 14,
) -> dict[str, Any]:
    """純函數：把 signal 對上 D0+N 實際報酬，算命中率。

    Args:
        analyses: [{id, symbol, signal('BUY'/'SELL'), confidence(float|None), created_at(datetime)}]
        prices_by_symbol: {symbol: [(date, px)]}（date 升冪；px 已 COALESCE 還原價）
        horizon_days: 報酬視窗（日曆天）。
    """
    rows: list[dict[str, Any]] = []

    def _blank() -> dict[str, Any]:
        return {"scored": 0, "hits": 0, "sum_return": 0.0}

    agg = {"BUY": _blank(), "SELL": _blank()}
    pending = 0
    no_data = 0

    for a in analyses:
        symbol = a["symbol"]
        signal = a["signal"]
        created = a["created_at"]
        d0 = created.astimezone(UTC).date() if isinstance(created, datetime) else created
        target = d0 + timedelta(days=horizon_days)

        bars = prices_by_symbol.get(symbol) or []
        row: dict[str, Any] = {
            "id": str(a["id"]),
            "symbol": symbol,
            "signal": signal,
            "confidence": a.get("confidence"),
            "created_at": created.isoformat() if isinstance(created, datetime) else str(created),
            "horizon_days": horizon_days,
            "entry_date": None,
            "entry_price": None,
            "exit_date": None,
            "exit_price": None,
            "actual_return": None,
            "hit": None,
            "status": "no_data",
        }

        if not bars:
            no_data += 1
            rows.append(row)
            continue

        dates = [b[0] for b in bars]
        latest = dates[-1]

        ei = _pick_entry(dates, d0, entry_tol_days)
        if ei is None:
            no_data += 1
            rows.append(row)
            continue

        xi, status = _pick_exit(dates, target, exit_tol_days, latest)
        if xi is None:
            row["status"] = status
            if status == "pending":
                pending += 1
            else:
                no_data += 1
            # 進場資訊仍可揭露（幫助 debug）
            row["entry_date"] = dates[ei].isoformat()
            row["entry_price"] = float(bars[ei][1])
            rows.append(row)
            continue

        entry_px = bars[ei][1]
        exit_px = bars[xi][1]
        if entry_px <= 0:
            no_data += 1
            row["status"] = "no_data"
            rows.append(row)
            continue

        ret = float((exit_px - entry_px) / entry_px)
        hit = ret > 0 if signal == "BUY" else ret < 0

        row.update(
            {
                "entry_date": dates[ei].isoformat(),
                "entry_price": float(entry_px),
                "exit_date": dates[xi].isoformat(),
                "exit_price": float(exit_px),
                "actual_return": ret,
                "hit": hit,
                "status": "scored",
            }
        )
        rows.append(row)

        side = agg[signal]
        side["scored"] += 1
        side["sum_return"] += ret
        if hit:
            side["hits"] += 1

    def _finalize(side: dict[str, Any]) -> dict[str, Any]:
        n = side["scored"]
        return {
            "scored": n,
            "hits": side["hits"],
            "hit_rate": (side["hits"] / n) if n else 0.0,
            "avg_return": (side["sum_return"] / n) if n else 0.0,
        }

    buy = _finalize(agg["BUY"])
    sell = _finalize(agg["SELL"])
    total_scored = buy["scored"] + sell["scored"]
    total_hits = buy["hits"] + sell["hits"]

    return {
        "horizon_days": horizon_days,
        "overall": {
            "scored": total_scored,
            "hits": total_hits,
            "hit_rate": (total_hits / total_scored) if total_scored else 0.0,
        },
        "buy": buy,
        "sell": sell,
        "pending": pending,
        "no_data": no_data,
        "rows": rows,
    }


async def compute_accuracy(
    session: AsyncSession,
    *,
    user_id: UUID,
    horizon_days: int = 30,
    lookback_days: int = 180,
    entry_tol_days: int = 14,
    exit_tol_days: int = 14,
) -> dict[str, Any]:
    """從 DB 撈使用者自己的已完成分析 + 本地日 K，算真實命中率（user-scoped）。

    2 次查詢避免 N+1：先撈分析、再一次撈這些 symbol 在所需日期範圍的日 K。
    """
    since = datetime.now(tz=UTC) - timedelta(days=lookback_days)

    a_stmt = (
        select(
            AnalysisReport.id,
            AnalysisReport.symbol,
            AnalysisReport.signal,
            AnalysisReport.confidence,
            AnalysisReport.created_at,
        )
        .where(
            AnalysisReport.user_id == user_id,
            AnalysisReport.status == "completed",
            AnalysisReport.signal.in_(("BUY", "SELL")),
            AnalysisReport.created_at >= since,
        )
        .order_by(AnalysisReport.created_at.desc())
        .limit(_MAX_ANALYSES)
    )
    a_res = await session.execute(a_stmt)
    analyses = [
        {
            "id": r.id,
            "symbol": r.symbol,
            "signal": r.signal,
            "confidence": float(r.confidence) if r.confidence is not None else None,
            "created_at": r.created_at,
        }
        for r in a_res
    ]

    if not analyses:
        return score_analyses(
            [],
            {},
            horizon_days=horizon_days,
            entry_tol_days=entry_tol_days,
            exit_tol_days=exit_tol_days,
        )

    symbols = sorted({a["symbol"] for a in analyses})
    d0s = [a["created_at"].astimezone(UTC).date() for a in analyses]
    range_lo = min(d0s) - timedelta(days=entry_tol_days)
    range_hi = max(d0s) + timedelta(days=horizon_days + exit_tol_days)

    px_col = func.coalesce(StockPrice.adjusted_close, StockPrice.close)
    p_stmt = (
        select(StockPrice.symbol, StockPrice.date, px_col.label("px"))
        .where(
            StockPrice.symbol.in_(symbols),
            StockPrice.date >= range_lo,
            StockPrice.date <= range_hi,
        )
        .order_by(StockPrice.symbol, StockPrice.date)
    )
    p_res = await session.execute(p_stmt)
    prices_by_symbol: dict[str, list[tuple[date_type, Decimal]]] = {}
    for sym, d, px in p_res:
        prices_by_symbol.setdefault(sym, []).append((d, px))

    return score_analyses(
        analyses,
        prices_by_symbol,
        horizon_days=horizon_days,
        entry_tol_days=entry_tol_days,
        exit_tol_days=exit_tol_days,
    )


__all__ = ["compute_accuracy", "score_analyses"]

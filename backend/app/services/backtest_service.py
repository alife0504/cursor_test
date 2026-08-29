"""績效統計 — 真實回測引擎（策略 vs 歷史日 K，PIT 正確）。

PIT / 無前視原則：
- 每日部位在「當日收盤」用**截至當日**的收盤價決策；報酬計入**隔日**
  （close[j]→close[j+1]），即今天的訊號賺明天的錢，不會用未來 bar 決定今天。
- 指標（SMA/EMA/MACD/RSI）只吃截至當日的序列；顯示視窗前會多抓 60 天暖身，
  讓視窗第一天起的部位已是穩定訊號，而非暖身期的雜訊。
- 現金部位報酬 0（不計利息）；long/cash（不放空），符合台股散戶 + SELL=退場持現金。

指標：SMA 交叉(5/20)、MACD(12/26/9)、RSI(14) 均值回歸(<30進>70出)、Buy&Hold。
另外一律計算同標的 Buy&Hold 作為基準線比較。
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import StockPrice

# 策略清單（與前端同步；value 為 API 參數）
STRATEGIES = ("buy_and_hold", "sma_cross", "macd_crossover", "rsi_mean_reversion")

# period → 顯示視窗（日曆天）；None = 全部可得
PERIOD_DAYS: dict[str, int | None] = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "all": None,
}

_WARMUP_DAYS = 60
_TRADING_DAYS_PER_YEAR = 252


# ─────────────────────── 指標 ───────────────────────


def _sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def _ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or not values:
        return out
    k = 2.0 / (period + 1)
    ema: float | None = None
    for i, v in enumerate(values):
        ema = v if ema is None else (v - ema) * k + ema
        # 暖身：前 period-1 根不視為穩定
        if i >= period - 1:
            out[i] = ema
    return out


def _rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        ch = values[i] - values[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_from(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        ch = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(ch, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-ch, 0.0)) / period
        out[i] = _rsi_from(avg_gain, avg_loss)
    return out


def _rsi_from(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


# ─────────────────────── 部位（pos[j]=close[j]→close[j+1] 期間持有 1/0） ───


def _positions(strategy: str, closes: list[float]) -> list[int]:
    n = len(closes)
    if strategy == "buy_and_hold":
        return [1] * n

    if strategy == "sma_cross":
        short = _sma(closes, 5)
        long = _sma(closes, 20)
        pos = []
        for j in range(n):
            s, ll = short[j], long[j]
            pos.append(1 if (s is not None and ll is not None and s > ll) else 0)
        return pos

    if strategy == "macd_crossover":
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        macd: list[float | None] = [
            (a - b) if (a is not None and b is not None) else None
            for a, b in zip(ema12, ema26, strict=False)
        ]
        macd_vals = [m if m is not None else 0.0 for m in macd]
        signal = _ema(macd_vals, 9)
        pos = []
        for j in range(n):
            m, sg = macd[j], signal[j]
            pos.append(1 if (m is not None and sg is not None and m > sg) else 0)
        return pos

    if strategy == "rsi_mean_reversion":
        rsi = _rsi(closes, 14)
        pos = []
        holding = 0
        for j in range(n):
            r = rsi[j]
            if r is not None:
                if holding == 0 and r < 30:
                    holding = 1
                elif holding == 1 and r > 70:
                    holding = 0
            pos.append(holding)
        return pos

    raise ValueError(f"未知策略：{strategy}")


# ─────────────────────── 權益曲線 + 指標 ───────────────────────


def _equity_and_metrics(
    dates: list[date_type],
    closes: list[float],
    pos: list[int],
    start_idx: int,
    initial_capital: float,
) -> dict[str, Any]:
    """自 start_idx 起建權益曲線；pos[i-1] 決定第 i 天報酬。"""
    curve: list[dict[str, Any]] = []
    daily_returns: list[float] = []
    eq = initial_capital
    peak = initial_capital
    curve.append({"date": dates[start_idx].isoformat(), "equity": round(eq, 2), "drawdown": 0.0})
    # 交易分組（連續持有為一筆）
    trades: list[float] = []
    cur_trade = 1.0
    in_trade = False

    for i in range(start_idx + 1, len(closes)):
        held = pos[i - 1] == 1
        r = (closes[i] / closes[i - 1] - 1.0) if held and closes[i - 1] > 0 else 0.0
        eq *= 1.0 + r
        daily_returns.append(r)
        if held:
            if not in_trade:
                in_trade = True
                cur_trade = 1.0
            cur_trade *= 1.0 + r
        else:
            if in_trade:
                trades.append(cur_trade - 1.0)
                in_trade = False
        peak = max(peak, eq)
        dd = (eq / peak - 1.0) if peak > 0 else 0.0
        curve.append(
            {
                "date": dates[i].isoformat(),
                "equity": round(eq, 2),
                "drawdown": round(dd * 100, 2),
            }
        )
    if in_trade:
        trades.append(cur_trade - 1.0)

    n_days = len(curve)
    total_return = eq / initial_capital - 1.0
    ann_return = (
        (eq / initial_capital) ** (_TRADING_DAYS_PER_YEAR / max(n_days - 1, 1)) - 1.0
        if eq > 0
        else -1.0
    )
    sharpe = _sharpe(daily_returns)
    max_dd = min((c["drawdown"] for c in curve), default=0.0) / 100.0
    wins = sum(1 for t in trades if t > 0)
    win_rate = (wins / len(trades)) if trades else 0.0
    # 盈虧比（profit factor）＝ 獲利交易報酬總和 / |虧損交易報酬總和|。
    # >1 代表整體賺、<1 賠；無虧損交易時給 None（避免除以 0 呈現 inf）。
    gross_profit = sum(t for t in trades if t > 0)
    gross_loss = -sum(t for t in trades if t < 0)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    return {
        "curve": curve,
        "metrics": {
            "total_return": total_return,
            "annualized_return": ann_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "num_trades": len(trades),
            "profit_factor": profit_factor,
        },
    }


def _sharpe(daily_returns: list[float]) -> float:
    n = len(daily_returns)
    if n < 2:
        return 0.0
    mean = sum(daily_returns) / n
    var = sum((r - mean) ** 2 for r in daily_returns) / (n - 1)
    sd = var**0.5
    if sd == 0:
        return 0.0
    return (mean / sd) * (_TRADING_DAYS_PER_YEAR**0.5)


def run_backtest(
    dates: list[date_type],
    closes: list[float],
    *,
    strategy: str,
    window_start: date_type,
    initial_capital: float = 1_000_000.0,
) -> dict[str, Any]:
    """純函數：對 (dates, closes) 跑策略回測，並附同標的 Buy&Hold 基準。

    dates/closes 需含 window_start 之前的暖身資料；輸出曲線自 window_start 起。
    """
    if not closes:
        return {"error": "no_data", "curve": [], "benchmark_curve": []}

    # 顯示視窗起點：第一個 date >= window_start（無則用第 0 根）
    start_idx = next((i for i, d in enumerate(dates) if d >= window_start), 0)

    # 防呆：視窗內至少要有 2 根 K 才算得出報酬；否則明確回 error 而非靜默回 0% 單點曲線
    if start_idx >= len(dates) - 1:
        return {
            "error": "insufficient_data",
            "curve": [],
            "benchmark_curve": [],
            "start_date": dates[start_idx].isoformat(),
            "end_date": dates[-1].isoformat(),
        }

    pos = _positions(strategy, closes)
    strat = _equity_and_metrics(dates, closes, pos, start_idx, initial_capital)

    bh_pos = [1] * len(closes)
    bench = _equity_and_metrics(dates, closes, bh_pos, start_idx, initial_capital)

    return {
        "strategy": strategy,
        "start_date": dates[start_idx].isoformat(),
        "end_date": dates[-1].isoformat(),
        "trading_days": len(strat["curve"]),
        "initial_capital": initial_capital,
        "curve": strat["curve"],
        "metrics": strat["metrics"],
        "benchmark_curve": [{"date": c["date"], "equity": c["equity"]} for c in bench["curve"]],
        "benchmark_metrics": bench["metrics"],
    }


#: 大盤基準代號（加權指數）。TAIEX B&H 作為「策略 vs 大盤」的市場基準。
_MARKET_INDEX_SYMBOL = "TAIEX"


async def _market_benchmark(
    session: AsyncSession,
    window_start: date_type,
    latest: date_type,
    initial_capital: float,
) -> dict[str, Any] | None:
    """大盤(TAIEX) Buy&Hold 基準：equity = 初始資金 × TAIEX_t / TAIEX_起點。

    資料不足（無 TAIEX 或視窗內 <2 根）時回 None（graceful，不擋回測主結果）。
    與個股同用 COALESCE(adjusted_close, close) 與同一視窗，口徑一致、PIT 安全。
    """
    px_col = func.coalesce(StockPrice.adjusted_close, StockPrice.close)
    rows = (
        await session.execute(
            select(StockPrice.date, px_col.label("px"))
            .where(
                StockPrice.symbol == _MARKET_INDEX_SYMBOL,
                StockPrice.date >= window_start,
                StockPrice.date <= latest,
            )
            .order_by(StockPrice.date)
        )
    ).all()
    if len(rows) < 2:
        return None
    dates = [r.date for r in rows]
    closes = [float(r.px) for r in rows]
    bh = _equity_and_metrics(dates, closes, [1] * len(closes), 0, initial_capital)
    return {
        "curve": [{"date": c["date"], "equity": c["equity"]} for c in bh["curve"]],
        "metrics": bh["metrics"],
    }


async def compute_backtest(
    session: AsyncSession,
    *,
    symbol: str,
    strategy: str,
    period: str = "3m",
    initial_capital: float = 1_000_000.0,
) -> dict[str, Any]:
    """從 stock_prices 抓日 K（含 60 天暖身）並跑回測。

    - 以該標的「最新可得日」為終點；window_start = 最新日 - period 天。
    - 報酬用 COALESCE(adjusted_close, close)：有還原價＝含息；否則原始收盤（除息跳空計入）。
      現況：美股已提供還原價、台股尚未回填（後續強化項）。基準一致、PIT 安全。
    """
    if strategy not in STRATEGIES:
        return {"error": "unknown_strategy", "curve": [], "benchmark_curve": []}

    px_col = func.coalesce(StockPrice.adjusted_close, StockPrice.close)

    latest = await session.scalar(
        select(func.max(StockPrice.date)).where(StockPrice.symbol == symbol)
    )
    if latest is None:
        return {"error": "no_data", "symbol": symbol, "curve": [], "benchmark_curve": []}

    period_days = PERIOD_DAYS.get(period, 90)
    if period_days is None:
        # "all"：全部可得 → 視窗起點取「最早可得日」，而非 latest（否則曲線退化成單點/0%）
        earliest = await session.scalar(
            select(func.min(StockPrice.date)).where(StockPrice.symbol == symbol)
        )
        window_start = earliest or latest
    else:
        window_start = latest - timedelta(days=period_days)
    fetch_from = window_start - timedelta(days=_WARMUP_DAYS)

    stmt = (
        select(StockPrice.date, px_col.label("px"))
        .where(
            StockPrice.symbol == symbol,
            StockPrice.date >= fetch_from,
            StockPrice.date <= latest,
        )
        .order_by(StockPrice.date)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return {"error": "no_data", "symbol": symbol, "curve": [], "benchmark_curve": []}

    dates = [r.date for r in rows]
    closes = [float(r.px) for r in rows]

    result = run_backtest(
        dates,
        closes,
        strategy=strategy,
        window_start=window_start,
        initial_capital=initial_capital,
    )
    result["symbol"] = symbol
    result["period"] = period

    # 真大盤(TAIEX)基準：讓「策略 vs 大盤」成立（原本只有同標的 B&H＝續抱基準）。
    # 用回測實際區間 [start_date, end_date] 對齊；資料不足則不附（前端據 in 判斷是否顯示）。
    if not result.get("error"):
        actual_start = date_type.fromisoformat(result["start_date"])
        market = await _market_benchmark(session, actual_start, latest, initial_capital)
        if market:
            result["market_benchmark_curve"] = market["curve"]
            result["market_benchmark_metrics"] = market["metrics"]
    return result


__all__ = ["PERIOD_DAYS", "STRATEGIES", "compute_backtest", "run_backtest"]

"""自動選股預篩選服務（v1.1）。

在昂貴的多 Agent pipeline 前，先用**純數據查詢（不呼叫 LLM）**把候選股票篩到少量，
避免浪費資源。設計拍板（見記憶 project_tradingagents_tw）：

- **保證比例**：依綜合評分排序後取前 N 檔，不論市況一定留下對應數量。
- **只用價量技術面**：全部因子來自 stock_prices（流動性 / 均線 / RSI / 漲幅 / 量能波動），
  基本面 + 籌碼（EPS/ROE/三大法人）待資料物化後再納入。
- **等級 → 數量**：以 `SCREEN_BASE_COUNT`（基本）為基準，低/中/高各留 2/3、1/2、1/3。
- **漸進疊加**：愈高等級評分納入愈多因子（趨勢 → 動能 → 量能/波動品質）、留得愈少。

⚠️ 這裡的門檻 / 權重 / 數量都是「條件」，刻意集中在檔案頂部常數，方便日後微調。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.price import StockPrice
from app.models.stock import StockList

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# ── 篩選等級 ──────────────────────────────────────────
# 「基本」是必備 floor（剔除停牌/低流動性/雞蛋水餃股），永遠先套用產生候選池，
# 不是使用者可選等級。低/中/高才是可選等級，各保留約 N 檔（絕對數）。
SCREEN_LEVELS = ("low", "mid", "high")
"""與前端 ScreenLevelChooser 的 ScreenLevel 對齊（不含 basic）。"""

# 等級 → 評分納入的因子權重（值愈高愈重要；0 = 不納入）。條件，可調。
_LEVEL_WEIGHTS: dict[str, dict[str, float]] = {
    # 低級：流動性 + 趨勢
    "low": {"liquidity": 0.5, "trend": 0.5},
    # 中級：+ 動能
    "mid": {"liquidity": 0.34, "trend": 0.33, "momentum": 0.33},
    # 高級：+ 量能 / 波動品質
    "high": {"liquidity": 0.25, "trend": 0.25, "momentum": 0.25, "quality": 0.25},
}

_TW_MARKETS = ("TWSE", "TPEX")
_US_MARKETS = ("NYSE", "NASDAQ", "AMEX")


def _markets_for(region: str) -> tuple[str, ...]:
    return _US_MARKETS if region.upper() == "US" else _TW_MARKETS


def target_count(level: str) -> int:
    """等級 → 實際保留檔數（絕對數，至少 1）。條件來自 settings，可調。"""
    counts = {
        "low": settings.SCREEN_COUNT_LOW,
        "mid": settings.SCREEN_COUNT_MID,
        "high": settings.SCREEN_COUNT_HIGH,
    }
    return max(1, int(counts.get(level, settings.SCREEN_COUNT_HIGH)))


@dataclass(slots=True)
class Candidate:
    """單一候選股票 + 已算好的價量指標。"""

    symbol: str
    market: str
    name: str | None = None
    last_close: float | None = None
    avg_turnover: float | None = None  # 近 N 日日均成交額（元）
    ma20: float | None = None
    ma60: float | None = None
    ret20: float | None = None  # 近 20 日報酬率
    rsi14: float | None = None
    volatility: float | None = None  # 近 20 日日報酬標準差
    vol_ratio: float | None = None  # 近 5 日均量 / 近 20 日均量


# ════════════════ 純函式評分（可單測、不碰 DB）════════════════


def _percentile_ranks(values: list[float | None]) -> list[float]:
    """把一組數值轉成 [0,1] 百分位排名（None → 0=最差）。

    同值取平均排名；空/單一元素安全處理。
    """
    n = len(values)
    if n == 0:
        return []
    # 升冪排名（最差在前）：None 視為最差排最前，其餘依值大小
    indexed = sorted(
        range(n),
        key=lambda i: (values[i] is not None, values[i] if values[i] is not None else 0.0),
    )
    ranks = [0.0] * n
    for rank_pos, orig_i in enumerate(indexed):
        # 百分位：最差 0、最佳 1
        ranks[orig_i] = rank_pos / (n - 1) if n > 1 else 1.0
    # None 一律壓到 0
    for i, v in enumerate(values):
        if v is None:
            ranks[i] = 0.0
    return ranks


def _rsi_health(rsi: float | None) -> float | None:
    """RSI 健康度 [0,1]：45~65 最佳，>70 超買 / <30 超賣扣分。"""
    if rsi is None:
        return None
    if 45.0 <= rsi <= 65.0:
        return 1.0
    if rsi > 70.0 or rsi < 30.0:
        return 0.2
    # 30~45 或 65~70 之間線性過渡
    if rsi < 45.0:
        return 0.2 + 0.8 * (rsi - 30.0) / 15.0
    return 0.2 + 0.8 * (70.0 - rsi) / 5.0


def _trend_signal(c: Candidate) -> float | None:
    """趨勢原始分：站上季線幅度 + 均線多頭排列 bonus。"""
    if c.last_close is None or c.ma60 is None or c.ma60 <= 0:
        return None
    above = c.last_close / c.ma60 - 1.0  # 站上季線幅度
    bonus = 0.0
    if c.ma20 is not None and c.ma20 > c.ma60:  # 多頭排列
        bonus = 0.05
    return above + bonus


def _quality_signal(c: Candidate) -> float | None:
    """量能 / 波動品質原始分：帶量（vol_ratio）+ 低波動（波動倒數）。"""
    parts: list[float] = []
    if c.vol_ratio is not None:
        parts.append(min(c.vol_ratio, 3.0))  # 帶量，封頂避免暴衝主導
    if c.volatility is not None and c.volatility > 0:
        parts.append(1.0 / (1.0 + c.volatility))  # 波動愈低分愈高
    if not parts:
        return None
    return sum(parts) / len(parts)


def select_candidates(candidates: list[Candidate], level: str) -> list[Candidate]:
    """依等級對候選股綜合評分、排序，取前 N 檔（低/中/高＝約 600/300/150）。

    純函式：input 已算好指標的 Candidate，output 排序後的子集。不碰 DB。
    """
    if not candidates:
        return []
    level = level if level in _LEVEL_WEIGHTS else "high"
    weights = _LEVEL_WEIGHTS[level]

    # 各因子原始值 → 百分位排名（跨候選池正規化，避免尺度問題）
    liq = _percentile_ranks([c.avg_turnover for c in candidates])
    trend = _percentile_ranks([_trend_signal(c) for c in candidates])
    mom_ret = _percentile_ranks([c.ret20 for c in candidates])
    mom_rsi = [_rsi_health(c.rsi14) for c in candidates]
    quality = _percentile_ranks([_quality_signal(c) for c in candidates])

    scores: list[tuple[float, str, Candidate]] = []
    for i, c in enumerate(candidates):
        momentum = 0.5 * mom_ret[i] + 0.5 * (mom_rsi[i] if mom_rsi[i] is not None else 0.0)
        factor = {
            "liquidity": liq[i],
            "trend": trend[i],
            "momentum": momentum,
            "quality": quality[i],
        }
        score = sum(w * factor[name] for name, w in weights.items())
        # symbol 當 tie-breaker，確保結果穩定可重現
        scores.append((score, c.symbol, c))

    scores.sort(key=lambda t: (-t[0], t[1]))
    keep = target_count(level)
    return [c for _, _, c in scores[:keep]]


# ════════════════ DB：組候選池 + 算指標 ════════════════


class ScreeningService:
    """自動選股：從市場撈流動性候選池、算價量指標、依等級評分取前 N 檔。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def select_symbols(self, region: str, level: str) -> list[Candidate]:
        """回傳該市場、該等級篩選後應送分析的股票（含指標）。

        Args:
            region: "TW" | "US"
            level: "low" | "mid" | "high"
        """
        markets = _markets_for(region)
        pool_size = settings.SCREEN_POOL_SIZE

        # 1) 找該市場「最新交易日」— 用資料本身而非今天，避免 dev/stale 資料落空
        latest_stmt = (
            select(func.max(StockPrice.date))
            .join(StockList, StockList.symbol == StockPrice.symbol)
            .where(StockList.market.in_(markets))
        )
        latest_date = (await self.session.execute(latest_stmt)).scalar_one_or_none()
        if latest_date is None:
            logger.info("screening.no_price_data", region=region)
            return []
        cutoff = latest_date - timedelta(days=settings.SCREEN_LOOKBACK_DAYS)

        # 2) 流動性候選池：近期日均成交額前 pool_size 檔（帶價格 floor）
        shortlist = await self._liquid_shortlist(markets, cutoff, pool_size)
        if not shortlist:
            return []

        # 3) 撈候選池近 lookback 的日 K，算指標
        candidates = await self._build_candidates(shortlist, cutoff)

        # 4) 評分 + 取前 N（低/中/高＝約 600/300/150）
        selected = select_candidates(candidates, level)
        logger.info(
            "screening.selected",
            region=region,
            level=level,
            pool=len(candidates),
            kept=len(selected),
        )
        return selected

    async def _liquid_shortlist(
        self, markets: tuple[str, ...], cutoff, pool_size: int
    ) -> list[str]:
        """近期日均成交額前 N 的 symbol（過濾價格 floor；若全被濾則放寬）。"""
        avg_to = func.avg(StockPrice.turnover)
        last_close = func.max(StockPrice.close)  # 近似最新價（floor 用，非精確）
        base = (
            select(StockPrice.symbol, avg_to.label("avg_to"))
            .join(StockList, StockList.symbol == StockPrice.symbol)
            .where(
                and_(
                    StockList.market.in_(markets),
                    StockList.is_active.is_(True),
                    StockPrice.date >= cutoff,
                )
            )
            .group_by(StockPrice.symbol)
        )
        floored = (
            base.having(
                and_(
                    avg_to >= settings.SCREEN_MIN_AVG_TURNOVER,
                    last_close >= settings.SCREEN_MIN_PRICE,
                )
            )
            .order_by(avg_to.desc())
            .limit(pool_size)
        )
        rows = (await self.session.execute(floored)).all()
        if not rows:
            # 安全網：floor 把池清空（如 dev 資料成交額偏低）→ 放寬價格/門檻，
            # 但仍要求「成交額 > 0」（否則 NULL turnover 在 DESC 會 NULLS FIRST 排最前，
            # 反而優先選到零流動性、無法交易的股票）。
            relaxed = base.having(avg_to > 0).order_by(avg_to.desc()).limit(pool_size)
            rows = (await self.session.execute(relaxed)).all()
        return [r.symbol for r in rows]

    async def _build_candidates(self, symbols: list[str], cutoff) -> list[Candidate]:
        """撈這批 symbol 的日 K + 名稱，逐檔算指標。"""
        # 名稱 / market
        meta_stmt = select(StockList.symbol, StockList.market, StockList.name).where(
            StockList.symbol.in_(symbols)
        )
        meta = {r.symbol: (r.market, r.name) for r in (await self.session.execute(meta_stmt)).all()}
        # 日 K（升冪，方便算序列）
        bars_stmt = (
            select(
                StockPrice.symbol,
                StockPrice.date,
                StockPrice.close,
                StockPrice.volume,
                StockPrice.turnover,
            )
            .where(and_(StockPrice.symbol.in_(symbols), StockPrice.date >= cutoff))
            .order_by(StockPrice.symbol.asc(), StockPrice.date.asc())
        )
        series: dict[str, list[tuple[float, float, float]]] = {}
        for r in (await self.session.execute(bars_stmt)).all():
            close = float(r.close) if r.close is not None else 0.0
            vol = float(r.volume) if r.volume is not None else 0.0
            to = float(r.turnover) if r.turnover is not None else 0.0
            series.setdefault(r.symbol, []).append((close, vol, to))

        out: list[Candidate] = []
        for sym in symbols:
            bars = series.get(sym, [])
            market, name = meta.get(sym, ("OTHER", None))
            out.append(_compute_indicators(sym, market, name, bars))
        return out


def _sma(values: list[float], n: int) -> float | None:
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _stdev(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def _compute_indicators(
    symbol: str, market: str, name: str | None, bars: list[tuple[float, float, float]]
) -> Candidate:
    """從日 K 序列（升冪，(close, volume, turnover)）算出 Candidate 指標。"""
    closes = [b[0] for b in bars]
    vols = [b[1] for b in bars]
    turnovers = [b[2] for b in bars]

    c = Candidate(symbol=symbol, market=market, name=name)
    if not closes:
        return c
    c.last_close = closes[-1]
    if turnovers:
        c.avg_turnover = sum(turnovers[-20:]) / min(len(turnovers), 20)
    c.ma20 = _sma(closes, 20)
    c.ma60 = _sma(closes, 60)
    c.rsi14 = _rsi(closes, 14)
    if len(closes) >= 21 and closes[-21] > 0:
        c.ret20 = closes[-1] / closes[-21] - 1.0
    # 近 20 日日報酬序列 → 波動
    if len(closes) >= 21:
        rets = [
            closes[i] / closes[i - 1] - 1.0
            for i in range(len(closes) - 20, len(closes))
            if closes[i - 1] > 0
        ]
        c.volatility = _stdev(rets)
    # 量比：近 5 日均量 / 近 20 日均量
    if len(vols) >= 20:
        v5 = sum(vols[-5:]) / 5
        v20 = sum(vols[-20:]) / 20
        if v20 > 0:
            c.vol_ratio = v5 / v20
    return c


__all__ = [
    "SCREEN_LEVELS",
    "Candidate",
    "ScreeningService",
    "select_candidates",
    "target_count",
]

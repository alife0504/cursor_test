"""海外指數即時報價（延遲）—— 市場總覽 8 張卡裡的 5 個海外市場。

FinMind 沒有任何海外即時資料（查證：US/日本只有日頻 EOD、韓國連日線都沒有），所以海外
5 檔改用 yfinance「延遲報價」（約 15 分鐘），卡片會標「延遲 · 資料時間」。台股（加權/台指全/
台積電）仍走 FinMind 真 5 秒即時，兩者分開。

- 涵蓋：道瓊期貨 YM=F、那斯達克期貨 NQ=F、費城半導體 ^SOX、韓國 ^KS11、日經 ^N225。
  美股用「期貨」→ 台股盤中（美國半夜、現貨休市）仍能看到隔夜即時變動；費半無零售期貨故用
  現貨、盤中顯示昨夜美國收盤；韓國/日經在台股早盤本來就在交易。
- yfinance 是同步包，呼叫一律 run_in_executor 避免 block event loop（同 us/yfinance_source）。
- 整批快取 Redis 數十秒：yfinance 本來就延遲 15 分，打更快不會更新、只是被 Yahoo 擋。
  快取後上游用量與開幾個頁面無關。
- 回傳形狀對齊 FinMindRealtimeClient（available / as_of / cached / quotes[...]），前端 IndexCard
  可用同一條路徑消化。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis

logger = get_logger(__name__)

# 顯示名稱固定在後端，前端直接用（symbol 用 yfinance 代碼，前端以此當 key）
FOREIGN_INDICES: list[dict[str, str]] = [
    {"symbol": "YM=F", "name": "道瓊期貨"},
    {"symbol": "NQ=F", "name": "那斯達克期貨"},
    {"symbol": "^SOX", "name": "費城半導體"},
    {"symbol": "^KS11", "name": "韓國 KOSPI"},
    {"symbol": "^N225", "name": "日經 225"},
]

_CACHE_KEY = "cache:realtime:foreign:all"
# yfinance 延遲 ~15 分，30 秒快取足夠新鮮；前端輪詢 60 秒（見 useRealtimeForeign）。
CACHE_TTL_S = 30


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (ValueError, TypeError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _fi_get(fi: Any, *keys: str) -> Any:
    """FastInfo 版本差異大：同時支援屬性（last_price）與字典（lastPrice）存取。"""
    for k in keys:
        try:
            v = getattr(fi, k)
            if v is not None:
                return v
        except Exception:  # noqa: S110 — 探測多種 FastInfo 存取風格，失敗就換下一種
            pass
        try:
            v = fi[k]
            if v is not None:
                return v
        except Exception:  # noqa: S110 — 同上
            pass
    return None


class ForeignRealtimeClient:
    """海外指數延遲報價（yfinance）。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_all(self) -> dict[str, Any]:
        # 1) 讀快取
        redis = None
        try:
            redis = await get_redis(RedisDB.CACHE)
            cached = await redis.get(_CACHE_KEY)
            if cached:
                payload = json.loads(cached)
                payload["cached"] = True
                return payload
        except Exception as exc:
            logger.warning("foreign_realtime.cache_read_failed", error=str(exc))

        # 2) 打 yfinance（同步 → executor）
        loop = asyncio.get_running_loop()
        try:
            quotes = await loop.run_in_executor(None, self._fetch_sync)
        except Exception as exc:
            logger.warning("foreign_realtime.fetch_failed", error=str(exc))
            return {
                "available": False,
                "reason": "upstream_error",
                "as_of": None,
                "cached": False,
                "quotes": [],
            }

        payload = {
            "available": True,
            "reason": None,
            "as_of": datetime.now(UTC).isoformat(),
            "cached": False,
            "quotes": quotes,
        }

        # 3) 寫快取
        if redis is not None and quotes:
            try:
                await redis.set(_CACHE_KEY, json.dumps(payload), ex=CACHE_TTL_S)
            except Exception as exc:
                logger.warning("foreign_realtime.cache_write_failed", error=str(exc))
        return payload

    def _fetch_sync(self) -> list[dict[str, Any]]:
        """在 executor thread 內同步抓 5 檔 fast_info。單檔失敗不影響其他（回 price=None）。"""
        import yfinance as yf

        out: list[dict[str, Any]] = []
        for spec in FOREIGN_INDICES:
            sym, name = spec["symbol"], spec["name"]
            try:
                fi = yf.Ticker(sym).fast_info
                price = _num(_fi_get(fi, "last_price", "lastPrice"))
                prev = _num(_fi_get(fi, "previous_close", "previousClose"))
                change = change_rate = None
                if price is not None and prev not in (None, 0):
                    change = round(price - prev, 4)
                    change_rate = round((price - prev) / prev * 100, 4)
                out.append(
                    {
                        "symbol": sym,
                        "name": name,
                        "price": price,
                        "prev_close": prev,
                        "change": change,
                        "change_rate": change_rate,
                        "delayed": True,
                    }
                )
            except Exception as exc:
                logger.warning("foreign_realtime.symbol_failed", symbol=sym, error=str(exc))
                out.append(
                    {
                        "symbol": sym,
                        "name": name,
                        "price": None,
                        "change": None,
                        "change_rate": None,
                        "delayed": True,
                    }
                )
        return out


__all__ = ["FOREIGN_INDICES", "ForeignRealtimeClient"]

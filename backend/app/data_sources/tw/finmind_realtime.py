"""FinMind 即時盤 snapshot 客戶端 — 盤中即時報價（台股個股 + 台指期）。

端點（與一般 /v4/data 不同，各自獨立）：
- 台股即時：https://api.finmindtrade.com/api/v4/taiwan_stock_tick_snapshot
- 期貨即時：https://api.finmindtrade.com/api/v4/taiwan_futures_snapshot

⚠️ 權限：這兩個端點需要 FinMind「付費 Sponsor」等級 token。免費(register)等級呼叫會回
status=400「Your level is register. Please update your user level.」。因此本客戶端把
FinMind 回傳的 status 對映成結構化的 unavailable reason，讓上層可優雅降級（顯示「需升級
FinMind 等級」而非拋例外）。實際欄位命名以官方回傳為準；本層用多候選鍵 + raw passthrough
做防禦式正規化，Sponsor 開通後即使欄位命名略有差異也不會壞。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import Settings
from app.core.http_client import get_async_client, request_with_retry
from app.core.logging_config import get_logger

logger = get_logger(__name__)

STOCK_SNAPSHOT_URL = "https://api.finmindtrade.com/api/v4/taiwan_stock_tick_snapshot"
FUTURES_SNAPSHOT_URL = "https://api.finmindtrade.com/api/v4/taiwan_futures_snapshot"


# ── unavailable reason codes（上層/前端可據此顯示對應訊息）─────────────────
class Reason:
    DISABLED = "disabled"  # 設定未開啟 FINMIND_REALTIME_ENABLED
    NO_TOKEN = "no_token"  # noqa: S105 — 這是 reason code 不是密碼；未設定 FINMIND_TOKEN
    NO_SYMBOLS = "no_symbols"  # caller 未指定任何代號
    TIER_INSUFFICIENT = "tier_insufficient"  # 免費等級無權（需 Sponsor）
    QUOTA_EXCEEDED = "quota_exceeded"  # 配額用盡（402/429）
    AUTH_FAILED = "auth_failed"  # token 無效（401）
    UPSTREAM_ERROR = "upstream_error"  # 其他上游錯誤 / 連線失敗
    EMPTY = "empty"  # 呼叫成功但無資料（如非交易時段）


_REASON_MESSAGE_ZH: dict[str, str] = {
    Reason.DISABLED: "即時盤功能未啟用（設定 FINMIND_REALTIME_ENABLED=true 以開啟）",
    Reason.NO_TOKEN: "未設定 FinMind token",
    Reason.NO_SYMBOLS: "未指定查詢代號",
    Reason.TIER_INSUFFICIENT: "FinMind token 等級不足：即時 snapshot 需付費 Sponsor 等級",
    Reason.QUOTA_EXCEEDED: "FinMind API 配額已用盡，請稍後再試",
    Reason.AUTH_FAILED: "FinMind token 認證失敗",
    Reason.UPSTREAM_ERROR: "FinMind 即時服務暫時無法連線",
    Reason.EMPTY: "目前無即時報價（可能非交易時段）",
}


def _to_decimal(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_int(v: Any) -> int | None:
    d = _to_decimal(v)
    return int(d) if d is not None else None


def _pick(rec: dict[str, Any], *keys: str) -> Any:
    """回第一個存在且非 None 的 key 值（容忍 snake_case / PascalCase 命名差異）。"""
    for k in keys:
        if k in rec and rec[k] is not None:
            return rec[k]
    return None


def _unavailable(reason: str, *, detail: str | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "message": _REASON_MESSAGE_ZH.get(reason, reason),
        "detail": detail,
        "as_of": None,
        "quotes": [],
    }


def _map_status_to_reason(status: int, msg: str) -> str:
    """把 FinMind 回傳的 status/msg 對映成 unavailable reason。"""
    low = (msg or "").lower()
    if status == 401:
        return Reason.AUTH_FAILED
    if status in (402, 429) or "upper limit" in low or "reach the upper" in low:
        return Reason.QUOTA_EXCEEDED
    if "level" in low or "sponsor" in low or "update your user level" in low:
        return Reason.TIER_INSUFFICIENT
    return Reason.UPSTREAM_ERROR


class FinMindRealtimeClient:
    """FinMind 即時 snapshot 客戶端（stateless；每次呼叫建新 http client）。"""

    name = "finmind_realtime"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _token(self) -> str | None:
        tok = self.settings.FINMIND_TOKEN
        return tok.get_secret_value() if tok else None

    async def _call(self, url: str, data_ids: list[str]) -> dict[str, Any]:
        """呼叫單一 snapshot 端點；回 FinMind 原始 envelope 或結構化 unavailable。"""
        token = self._token()
        if not token:
            return _unavailable(Reason.NO_TOKEN)

        params: dict[str, Any] = {"token": token}
        if data_ids:
            # FinMind snapshot 端點以逗號分隔多代號
            params["data_id"] = ",".join(data_ids)

        client = get_async_client(name=self.name)
        try:
            async with client as c:
                resp = await request_with_retry(
                    c,
                    "GET",
                    url,
                    source_name=self.name,
                    raise_on_4xx=False,
                    params=params,
                )
        except httpx.HTTPStatusError as e:
            # 429 / 5xx 重試耗盡：request_with_retry 會 re-raise（非 RequestError 子類）
            st = e.response.status_code if e.response is not None else 0
            reason = _map_status_to_reason(st, str(e))
            logger.warning("finmind_realtime.http_status_error", url=url, status=st)
            return _unavailable(reason, detail=f"http {st}")
        except httpx.HTTPError as e:
            # 連線層失敗（DNS / refused / timeout 重試完）
            logger.warning("finmind_realtime.request_error", url=url, error=str(e))
            return _unavailable(Reason.UPSTREAM_ERROR, detail=str(e))

        try:
            body = resp.json()
        except ValueError:
            return _unavailable(
                Reason.UPSTREAM_ERROR, detail=f"non-json (status={resp.status_code})"
            )

        status = int(body.get("status", resp.status_code))
        msg = str(body.get("msg", "") or "")
        if status != 200:
            reason = _map_status_to_reason(status, msg)
            logger.info("finmind_realtime.unavailable", reason=reason, status=status, msg=msg)
            return _unavailable(reason, detail=msg or None)

        data = body.get("data") or []
        return {"ok": True, "data": data}

    @staticmethod
    def _normalize_stock(rec: dict[str, Any]) -> dict[str, Any]:
        """防禦式正規化台股即時 tick（多候選鍵；保留 raw 供 forward-compat）。"""
        return {
            "symbol": _pick(rec, "stock_id", "StockID", "data_id"),
            "price": _to_decimal(
                _pick(rec, "close", "Close", "last_price", "LastPrice", "deal_price")
            ),
            "open": _to_decimal(_pick(rec, "open", "Open")),
            "high": _to_decimal(_pick(rec, "high", "High")),
            "low": _to_decimal(_pick(rec, "low", "Low")),
            "change": _to_decimal(_pick(rec, "change", "Change")),
            "change_rate": _to_decimal(_pick(rec, "change_rate", "ChangeRate", "change_percent")),
            "volume": _to_int(_pick(rec, "volume", "Volume", "TickVolume")),
            "total_volume": _to_int(_pick(rec, "total_volume", "TotalVolume")),
            "amount": _to_decimal(_pick(rec, "amount", "Amount")),
            "total_amount": _to_decimal(_pick(rec, "total_amount", "TotalAmount")),
            "bid_price": _to_decimal(_pick(rec, "best_bid_price", "BidPrice", "bid_price")),
            "ask_price": _to_decimal(_pick(rec, "best_ask_price", "AskPrice", "ask_price")),
            "tick_type": _pick(rec, "tick_type", "TickType"),
            "time": _pick(rec, "date", "time", "TickTime", "datetime"),
            "raw": rec,
        }

    @staticmethod
    def _normalize_futures(rec: dict[str, Any]) -> dict[str, Any]:
        """防禦式正規化期貨即時 snapshot。"""
        out = FinMindRealtimeClient._normalize_stock(rec)
        # 期貨代號欄位名不同
        out["symbol"] = _pick(rec, "futures_id", "FuturesID", "contract_id", "data_id", "stock_id")
        return out

    async def fetch_stock_snapshot(self, symbols: list[str]) -> dict[str, Any]:
        """台股即時 tick snapshot。symbols 為股票代號 list（如 ['2330','2317']）。"""
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        symbols = [s.strip() for s in symbols if s and s.strip()]
        if not symbols:
            return _unavailable(Reason.NO_SYMBOLS)

        res = await self._call(STOCK_SNAPSHOT_URL, symbols)
        if not res.get("ok"):
            return res
        quotes = [self._normalize_stock(r) for r in res["data"]]
        if not quotes:
            return _unavailable(Reason.EMPTY)
        return {
            "available": True,
            "reason": None,
            "message": None,
            "detail": None,
            "as_of": quotes[0].get("time"),
            "quotes": quotes,
        }

    async def fetch_futures_snapshot(self, contract_ids: list[str]) -> dict[str, Any]:
        """台股期貨即時 snapshot。contract_ids 為期貨代號 list（如 ['TX','MTX']）。"""
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        contract_ids = [s.strip() for s in contract_ids if s and s.strip()]
        if not contract_ids:
            return _unavailable(Reason.NO_SYMBOLS)

        res = await self._call(FUTURES_SNAPSHOT_URL, contract_ids)
        if not res.get("ok"):
            return res
        quotes = [self._normalize_futures(r) for r in res["data"]]
        if not quotes:
            return _unavailable(Reason.EMPTY)
        return {
            "available": True,
            "reason": None,
            "message": None,
            "detail": None,
            "as_of": quotes[0].get("time"),
            "quotes": quotes,
        }


__all__ = ["FinMindRealtimeClient", "Reason"]

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
        return v if v.is_finite() else None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None
    # NaN / Infinity 是合法 Decimal（JSON 可能回 bare NaN），但後續 int() 會爆 → 一律當缺值
    return d if d.is_finite() else None


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

    async def _call(self, url: str, data_id: str | None) -> dict[str, Any]:
        """呼叫單一 snapshot 端點；回 FinMind 原始 envelope 或結構化 unavailable。

        data_id=None → 官方語意是「回全部」（實測台股一次回 2,851 檔）。
        ⚠️ 不可用逗號合併多代號：實測 `data_id=2330,2317` 會回 data:[]（靜默空結果）。
        """
        token = self._token()
        if not token:
            return _unavailable(Reason.NO_TOKEN)

        # 官方文件（API 使用說明 / llms-full.txt）明訂 V4 以
        # `Authorization: Bearer {token}` header 認證；query param ?token= 亦可通（實測
        # /data 端點成立），故兩者都送以求相容。注意 token 值本身不含 "Bearer " 前綴——
        # 前綴屬於 header 格式，誤寫進 token 會被判 "Token is illegal"。
        params: dict[str, Any] = {"token": token}
        if data_id:
            params["data_id"] = data_id

        # 即時報價要短 timeout：預設(connect 10s/read 30s)×3 retries 最壞會拖到 ~2 分鐘，
        # 而本呼叫期間 request 仍握著 rw DB 連線（get_current_user 依賴），會拖垮連線池。
        # 何況等 30 秒才拿到的「即時」報價也沒有意義。
        client = get_async_client(
            name=self.name,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=5.0),
        )
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

        # 上游/中介（proxy、WAF）可能回合法 JSON 但不是 dict（如 [] / null）→ .get 會 AttributeError
        if not isinstance(body, dict):
            return _unavailable(
                Reason.UPSTREAM_ERROR, detail=f"unexpected json body: {type(body).__name__}"
            )

        # status 可能是非數字（如 "error"）或 None → int() 會 ValueError/TypeError
        try:
            status = int(body.get("status", resp.status_code))
        except (TypeError, ValueError):
            return _unavailable(
                Reason.UPSTREAM_ERROR, detail=f"non-numeric status: {body.get('status')!r}"
            )

        msg = str(body.get("msg", "") or "")
        if status != 200:
            reason = _map_status_to_reason(status, msg)
            logger.info("finmind_realtime.unavailable", reason=reason, status=status, msg=msg)
            return _unavailable(reason, detail=msg or None)

        data = body.get("data") or []
        if not isinstance(data, list):
            return _unavailable(
                Reason.UPSTREAM_ERROR, detail=f"unexpected data type: {type(data).__name__}"
            )
        # 只留 dict 記錄；非 dict 元素會讓後續 _normalize_* 的 .get 爆掉
        return {"ok": True, "data": [r for r in data if isinstance(r, dict)]}

    @staticmethod
    def _normalize_stock(rec: dict[str, Any]) -> dict[str, Any]:
        """正規化台股即時 tick。

        欄位名以官方文件為準（https://finmind.github.io/llms-full.txt）：
        amount, average_price, buy_price, buy_volume, change_price, change_rate, close,
        high, low, open, sell_price, sell_volume, total_amount, total_volume, volume,
        volume_ratio, yesterday_volume, date, stock_id, TickType
        買/賣價官方用 buy_price / sell_price（非 bid/ask），漲跌用 change_price。
        仍保留其他候選鍵與 raw passthrough，以防官方欄位微調。
        """
        return {
            "symbol": _pick(rec, "stock_id", "StockID", "data_id"),
            "price": _to_decimal(_pick(rec, "close", "Close", "last_price", "deal_price")),
            "open": _to_decimal(_pick(rec, "open", "Open")),
            "high": _to_decimal(_pick(rec, "high", "High")),
            "low": _to_decimal(_pick(rec, "low", "Low")),
            "change": _to_decimal(_pick(rec, "change_price", "change", "Change")),
            "change_rate": _to_decimal(_pick(rec, "change_rate", "ChangeRate")),
            "average_price": _to_decimal(_pick(rec, "average_price")),
            "volume": _to_int(_pick(rec, "volume", "Volume")),
            "total_volume": _to_int(_pick(rec, "total_volume", "TotalVolume")),
            "yesterday_volume": _to_int(_pick(rec, "yesterday_volume")),
            "volume_ratio": _to_decimal(_pick(rec, "volume_ratio")),
            "amount": _to_decimal(_pick(rec, "amount", "Amount")),
            "total_amount": _to_decimal(_pick(rec, "total_amount", "TotalAmount")),
            "bid_price": _to_decimal(_pick(rec, "buy_price", "bid_price", "BidPrice")),
            "bid_volume": _to_int(_pick(rec, "buy_volume", "bid_volume", "BidVolume")),
            "ask_price": _to_decimal(_pick(rec, "sell_price", "ask_price", "AskPrice")),
            "ask_volume": _to_int(_pick(rec, "sell_volume", "ask_volume", "AskVolume")),
            "tick_type": _pick(rec, "TickType", "tick_type"),
            "time": _pick(rec, "date", "time", "datetime"),
            "raw": rec,
        }

    @staticmethod
    def _normalize_futures(rec: dict[str, Any]) -> dict[str, Any]:
        """正規化期貨即時 snapshot（欄位與個股相同，僅代號欄位是 futures_id）。"""
        out = FinMindRealtimeClient._normalize_stock(rec)
        out["symbol"] = _pick(rec, "futures_id", "FuturesID", "contract_id", "data_id", "stock_id")
        return out

    @staticmethod
    def _ok(quotes: list[dict[str, Any]]) -> dict[str, Any]:
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

    async def fetch_stock_snapshot(self, symbols: list[str]) -> dict[str, Any]:
        """台股即時 tick snapshot。symbols 為股票代號 list（如 ['2330','2317']）。

        單一代號 → 直接帶 data_id；多代號 → 一次抓全部（約 2,851 檔）再本地過濾。
        FinMind 不支援逗號合併多代號（會靜默回空），而「抓全部」不論幾檔都只花 1 次額度，
        比逐檔各發一次請求更省（Sponsor 6000 req/hr）。
        """
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        symbols = [s.strip() for s in symbols if s and s.strip()]
        if not symbols:
            return _unavailable(Reason.NO_SYMBOLS)

        single = symbols[0] if len(symbols) == 1 else None
        res = await self._call(STOCK_SNAPSHOT_URL, single)
        if not res.get("ok"):
            return res

        records = res["data"]
        if single is None:
            want = {s.upper() for s in symbols}
            records = [r for r in records if str(r.get("stock_id", "")).upper() in want]
        return self._ok([self._normalize_stock(r) for r in records])

    async def fetch_futures_snapshot(self, contract_ids: list[str]) -> dict[str, Any]:
        """台股期貨即時 snapshot。contract_ids 為期貨代號 list（如 ['TXF','MXF']）。

        注意 data_id=TXF 回的是各月份契約（futures_id 形如 `TXFR2`），故多代號過濾用
        prefix 比對而非完全相等。
        """
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        contract_ids = [s.strip() for s in contract_ids if s and s.strip()]
        if not contract_ids:
            return _unavailable(Reason.NO_SYMBOLS)

        single = contract_ids[0] if len(contract_ids) == 1 else None
        res = await self._call(FUTURES_SNAPSHOT_URL, single)
        if not res.get("ok"):
            return res

        records = res["data"]
        if single is None:
            prefixes = tuple(c.upper() for c in contract_ids)
            records = [
                r for r in records if str(r.get("futures_id", "")).upper().startswith(prefixes)
            ]
        return self._ok([self._normalize_futures(r) for r in records])


__all__ = ["FinMindRealtimeClient", "Reason"]

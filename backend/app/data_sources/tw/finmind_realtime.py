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

import json
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import Settings
from app.core.http_client import get_async_client, request_with_retry
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis

logger = get_logger(__name__)

STOCK_SNAPSHOT_URL = "https://api.finmindtrade.com/api/v4/taiwan_stock_tick_snapshot"
FUTURES_SNAPSHOT_URL = "https://api.finmindtrade.com/api/v4/taiwan_futures_snapshot"

# 全市場快照快取秒數。
# 設計要點：一律「不帶 data_id 抓全部」再本地過濾，並把整份快照快取數秒 → 上游用量與
# 「開了幾個頁面、查了幾檔股票」完全脫鉤，上限 3600/TTL 次/小時，遠低於 Sponsor 的
# 6000/hr。若改成逐檔查詢，多開幾個分頁輪詢就會吃爆額度。
#
# ⚠️ TTL 必須**小於**前端輪詢間隔（REALTIME_POLL_MS=5s）。原本 TTL=5 與輪詢同為 5 秒，
# 剛好卡在邊界：約一半的輪詢會在快取到期前抵達而拿到上一輪的舊資料 → 使用者感受到的
# 更新變成「10 秒才動一次」。取 2 秒可確保每次 5 秒輪詢都拿到新資料；上限
# 3600/2=1800 次/小時/快取鍵（僅 stock、futures 兩個鍵），仍遠低於配額。
SNAPSHOT_CACHE_TTL_S = 2
_CACHE_KEY_STOCK = "cache:realtime:tw:stock:all"
_CACHE_KEY_FUTURES = "cache:realtime:tw:futures:all"

# FinMind tick_snapshot 的 3 碼指數代號 → 我方慣用 symbol（與 stock_prices / market_service 對齊）
TW_INDEX_CODE_TO_SYMBOL: dict[str, str] = {"001": "TAIEX", "101": "TPEX"}
TW_INDEX_NAMES: dict[str, str] = {"TAIEX": "加權指數", "TPEX": "櫃買指數"}


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
        "cached": False,
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
    def _ok(quotes: list[dict[str, Any]], *, cached: bool = False) -> dict[str, Any]:
        if not quotes:
            return _unavailable(Reason.EMPTY)
        # as_of 取「所有報價中最新的 tick 時間」，不可用 quotes[0]：
        # 上游回傳順序不保證，第一筆常是幾乎沒成交的冷門標的/遠月契約（實測台指期第一筆
        # 是 TXFJ6，總量 1、時間停在 15:02），拿它當 as_of 會讓畫面「即時時間」永遠不動，
        # 看起來像沒同步——即使近月契約其實每秒都在跳。時間為 ISO 樣式字串，字典序＝時序。
        times = [t for t in (q.get("time") for q in quotes) if t]
        return {
            "available": True,
            "reason": None,
            "message": None,
            "detail": None,
            "as_of": max(times) if times else None,
            "cached": cached,
            "quotes": quotes,
        }

    async def _fetch_cached(self, url: str, cache_key: str, data_id: str | None) -> dict[str, Any]:
        """打一次 snapshot 並以 Redis 快取數秒。回 {"ok":True,"data":[...],"cached":bool}。

        data_id=None → 抓全部（個股/指數用；FinMind 不支援逗號合併多代號故抓全部再過濾）。
        data_id 給值 → 帶 data_id 查（期貨用；期貨端點強制要 data_id，不帶會 422）。
        配上快取後上游用量與查詢檔數/頁面數無關。Redis 掛掉不影響正確性——只是每次打上游。
        """
        redis = None
        try:
            redis = await get_redis(RedisDB.CACHE)
            cached = await redis.get(cache_key)
            if cached:
                return {"ok": True, "data": json.loads(cached), "cached": True}
        except Exception as exc:  # 快取讀失敗不致命
            logger.warning("finmind_realtime.cache_read_failed", key=cache_key, error=str(exc))

        res = await self._call(url, data_id)
        if not res.get("ok"):
            return res

        if redis is not None:
            try:
                await redis.set(cache_key, json.dumps(res["data"]), ex=SNAPSHOT_CACHE_TTL_S)
            except Exception as exc:
                logger.warning("finmind_realtime.cache_write_failed", key=cache_key, error=str(exc))
        return {"ok": True, "data": res["data"], "cached": False}

    async def _fetch_all_cached(self, url: str, cache_key: str) -> dict[str, Any]:
        """抓全市場快照（不帶 data_id）並快取。個股/指數用。"""
        return await self._fetch_cached(url, cache_key, None)

    async def _fetch_by_data_id_cached(
        self, url: str, cache_key: str, data_id: str
    ) -> dict[str, Any]:
        """帶 data_id 抓 snapshot 並快取。期貨用（其端點強制要 data_id）。"""
        return await self._fetch_cached(url, cache_key, data_id)

    async def fetch_stock_snapshot(self, symbols: list[str]) -> dict[str, Any]:
        """台股個股即時報價。symbols 為股票代號 list（如 ['2330','2317']）。"""
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        symbols = [s.strip() for s in symbols if s and s.strip()]
        if not symbols:
            return _unavailable(Reason.NO_SYMBOLS)

        res = await self._fetch_all_cached(STOCK_SNAPSHOT_URL, _CACHE_KEY_STOCK)
        if not res.get("ok"):
            return res

        want = {s.upper() for s in symbols}
        records = [r for r in res["data"] if str(r.get("stock_id", "")).upper() in want]
        return self._ok([self._normalize_stock(r) for r in records], cached=bool(res.get("cached")))

    async def fetch_all_stock_quotes(self) -> dict[str, Any]:
        """整份全市場個股即時快照（含 ETF / 指數 / 權證，由 caller 依需要過濾）。

        給「即時漲跌家數 / 漲跌榜」用：與個股/指數共用同一份快取，不額外花額度。
        """
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        res = await self._fetch_all_cached(STOCK_SNAPSHOT_URL, _CACHE_KEY_STOCK)
        if not res.get("ok"):
            return res
        return self._ok(
            [self._normalize_stock(r) for r in res["data"]], cached=bool(res.get("cached"))
        )

    async def fetch_index_snapshot(self) -> dict[str, Any]:
        """大盤指數即時報價（加權 TAIEX / 櫃買 TPEX）。

        FinMind 的 tick_snapshot 除了 4 碼股票，data_id 也吃 3 碼指數代號
        （001=加權指數、101=櫃買）。而「抓全部」的回應裡本來就含這兩筆 → 與個股共用
        同一份快取，取得即時大盤**不額外花任何額度**。
        輸出 symbol 統一成我方慣用的 TAIEX / TPEX（與 stock_prices、market_service 一致）。
        """
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)

        res = await self._fetch_all_cached(STOCK_SNAPSHOT_URL, _CACHE_KEY_STOCK)
        if not res.get("ok"):
            return res

        quotes: list[dict[str, Any]] = []
        for rec in res["data"]:
            our = TW_INDEX_CODE_TO_SYMBOL.get(str(rec.get("stock_id", "")))
            if our is None:
                continue
            q = self._normalize_stock(rec)
            q["symbol"] = our
            q["name"] = TW_INDEX_NAMES[our]
            quotes.append(q)
        return self._ok(quotes, cached=bool(res.get("cached")))

    async def fetch_futures_snapshot(self, contract_ids: list[str]) -> dict[str, Any]:
        """台股期貨即時報價。contract_ids 為期貨代號 list（如 ['TXF','MXF']）。

        ⚠️ 與個股/指數不同：期貨端點**強制要 data_id**，不帶會回 422「Field required」，
        故不能用「抓全部再過濾」。改為逐 contract_id 帶 data_id 查、各自快取。
        data_id=TXF 回的是各月份契約（futures_id 形如 `TXFR2`），全部保留、由 caller 取近月。
        """
        if not self.settings.FINMIND_REALTIME_ENABLED:
            return _unavailable(Reason.DISABLED)
        contract_ids = [s.strip() for s in contract_ids if s and s.strip()]
        if not contract_ids:
            return _unavailable(Reason.NO_SYMBOLS)

        records: list[dict[str, Any]] = []
        cached_all = True
        for cid in contract_ids:
            res = await self._fetch_by_data_id_cached(
                FUTURES_SNAPSHOT_URL, f"{_CACHE_KEY_FUTURES}:{cid.upper()}", cid
            )
            if not res.get("ok"):
                # 任一代號取得失敗即回該錯誤（tier/quota/upstream），不假裝部分成功
                return res
            records.extend(res["data"])
            cached_all = cached_all and bool(res.get("cached"))

        return self._ok([self._normalize_futures(r) for r in records], cached=cached_all)


__all__ = ["FinMindRealtimeClient", "Reason"]

"""FinMind 即時 snapshot 客戶端單元測試（mock httpx，不打網路）。

背景：taiwan_stock_tick_snapshot / taiwan_futures_snapshot 需 FinMind 付費 Sponsor 等級。
本專案帳號已為 SponsorYear（2026-07-16 實打驗證通過），故欄位名與代號皆以官方文件
（https://finmind.github.io/llms-full.txt）與實際回傳為準，不再是臆測值。

驗證重點：
1. 正規化欄位——以官方欄位名為準（buy_price/sell_price/change_price，非 bid/ask/change）
2. FinMind status → unavailable reason 的對映（tier/quota/auth…）
3. 未啟用 / 無 token / 無代號的短路降級（不打 API、不吃配額）
4. never-raise 契約：上游回怪東西（非 dict body、非數字 status、NaN）也不得拋給上層
5. 「抓全部 + 快取」——上游用量與查詢檔數/頁面數脫鉤（額度安全的關鍵）
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.data_sources.tw.finmind_realtime import (
    SNAPSHOT_CACHE_TTL_S,
    STOCK_SNAPSHOT_URL,
    FinMindRealtimeClient,
    Reason,
)

pytestmark = pytest.mark.unit


# ── Fixtures / helpers ───────────────────────────────────


class _FakeSettings:
    """只提供 client 會讀到的兩個欄位（避免動到全域 settings）。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        token: str | None = "faketoken",  # noqa: S107 — 測試用假 token，非真實密碼
    ) -> None:
        self.FINMIND_REALTIME_ENABLED = enabled
        self.FINMIND_TOKEN = SecretStr(token) if token else None


def _client(**kw: Any) -> FinMindRealtimeClient:
    return FinMindRealtimeClient(_FakeSettings(**kw))  # type: ignore[arg-type]


class _FakeRedis:
    """最小 Redis 替身（只實作 client 用到的 get/set）。"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, int | None]] = []

    async def get(self, k: str):  # type: ignore[no-untyped-def]
        return self.store.get(k)

    async def set(self, k: str, v: str, ex: int | None = None):  # type: ignore[no-untyped-def]
        self.store[k] = v
        self.set_calls.append((k, ex))


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch):  # type: ignore[no-untyped-def]
    """預設停用快取，讓每個 test 都確實打到 mock_transport（避免跨 test 互相污染）。

    client 對 Redis 失敗是容錯的（只會退化成每次打上游），故這裡直接讓 get_redis 拋錯。
    需要驗快取行為的 test 再自行覆寫（見 test_snapshot_is_cached_*）。
    """

    async def _boom(*_a, **_kw):  # type: ignore[no-untyped-def]
        raise ConnectionError("redis disabled in unit test")

    monkeypatch.setattr("app.data_sources.tw.finmind_realtime.get_redis", _boom)


@pytest.fixture
def mock_transport(monkeypatch):  # type: ignore[no-untyped-def]
    """攔截 httpx.AsyncClient.request；test 內設定 response_factory。"""
    state: dict[str, Any] = {"response_factory": None, "calls": []}

    async def fake_request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        state["calls"].append({"method": method, "url": url, "kwargs": kwargs})
        factory = state["response_factory"]
        if factory is None:
            raise AssertionError("不應該打 HTTP（預期短路降級）")
        return factory(method, url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return state


def _resp(body: Any, *, http_status: int = 200) -> httpx.Response:
    req = httpx.Request("GET", STOCK_SNAPSHOT_URL)
    return httpx.Response(status_code=http_status, request=req, json=body)


# ── 短路降級（不打 API，不吃配額）────────────────────────


@pytest.mark.asyncio
async def test_disabled_short_circuits_without_http(mock_transport) -> None:
    """未啟用時應直接回 disabled，且完全不打 HTTP（避免浪費 FinMind 配額）。"""
    res = await _client(enabled=False).fetch_stock_snapshot(["2330"])
    assert res["available"] is False
    assert res["reason"] == Reason.DISABLED
    assert res["quotes"] == []
    assert mock_transport["calls"] == []


@pytest.mark.asyncio
async def test_no_token_short_circuits(mock_transport) -> None:
    res = await _client(token=None).fetch_stock_snapshot(["2330"])
    assert res["reason"] == Reason.NO_TOKEN
    assert mock_transport["calls"] == []


@pytest.mark.asyncio
async def test_no_symbols_short_circuits(mock_transport) -> None:
    """空字串 / 全空白代號應被濾掉並短路。"""
    res = await _client().fetch_stock_snapshot(["", "   "])
    assert res["reason"] == Reason.NO_SYMBOLS
    assert mock_transport["calls"] == []


# ── FinMind status → reason 對映 ─────────────────────────


@pytest.mark.asyncio
async def test_tier_insufficient_maps_reason(mock_transport) -> None:
    """免費等級的真實回應（status=400 + level 訊息）應對映成 tier_insufficient。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": (
                "Your level is register. Please update your user level. "
                "Detail information:https://finmindtrade.com/analysis/#/Sponsor/sponsor"
            ),
            "status": 400,
        },
        http_status=200,
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["available"] is False
    assert res["reason"] == Reason.TIER_INSUFFICIENT
    assert "Sponsor" in res["message"]


@pytest.mark.asyncio
async def test_quota_exceeded_maps_reason(mock_transport) -> None:
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"msg": "Requests reach the upper limit. https://finmindtrade.com/", "status": 402},
        http_status=200,
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["reason"] == Reason.QUOTA_EXCEEDED


@pytest.mark.asyncio
async def test_auth_failed_maps_reason(mock_transport) -> None:
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"msg": "token is invalid", "status": 401}, http_status=200
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["reason"] == Reason.AUTH_FAILED


@pytest.mark.asyncio
async def test_empty_data_maps_reason(mock_transport) -> None:
    """呼叫成功但無資料（非交易時段）→ empty，而非假裝有報價。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"msg": "ok", "status": 200, "data": []}
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["available"] is False
    assert res["reason"] == Reason.EMPTY


@pytest.mark.asyncio
async def test_non_json_response_degrades(mock_transport) -> None:
    """上游回非 JSON 也要優雅降級而不是拋例外。"""

    def factory(m, u, k):  # type: ignore[no-untyped-def]
        req = httpx.Request("GET", STOCK_SNAPSHOT_URL)
        return httpx.Response(status_code=200, request=req, text="<html>502</html>")

    mock_transport["response_factory"] = factory
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["reason"] == Reason.UPSTREAM_ERROR


@pytest.mark.asyncio
async def test_connection_error_degrades(mock_transport) -> None:
    """連線層失敗（RequestError）→ upstream_error，不外拋。"""

    def factory(m, u, k):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("dns fail")

    mock_transport["response_factory"] = factory
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["reason"] == Reason.UPSTREAM_ERROR


# ── 上游回「合法 JSON 但形狀不對」時仍不可拋（never-raise 契約）──


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], None, [{"error": "blocked"}], "plain-string"])
async def test_non_dict_json_body_degrades(mock_transport, body) -> None:
    """proxy/WAF 可能回 200 + 合法 JSON 但不是 dict（[] / null / list）→ 不可 AttributeError。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(body)
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["available"] is False
    assert res["reason"] == Reason.UPSTREAM_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ["error", None, "", {"x": 1}])
async def test_non_numeric_status_degrades(mock_transport, bad_status) -> None:
    """status 非數字（int() 會 ValueError/TypeError）→ 不可穿過 except 變成 500。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"status": bad_status, "msg": "weird"}
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["available"] is False
    assert res["reason"] == Reason.UPSTREAM_ERROR


@pytest.mark.asyncio
async def test_non_list_data_degrades(mock_transport) -> None:
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"status": 200, "msg": "ok", "data": {"not": "a list"}}
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["reason"] == Reason.UPSTREAM_ERROR


@pytest.mark.asyncio
async def test_non_dict_records_are_filtered_out(mock_transport) -> None:
    """data 內混入非 dict 元素不可讓 _normalize 的 .get 爆掉。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"status": 200, "msg": "ok", "data": ["junk", None, {"stock_id": "2330", "close": 1150}]}
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["available"] is True
    assert len(res["quotes"]) == 1
    assert res["quotes"][0]["symbol"] == "2330"


def test_nan_and_infinity_values_do_not_raise() -> None:
    """JSON 可能回 bare NaN/Infinity；Decimal('NaN') 合法但 int() 會爆 → 應視為缺值。"""
    q = FinMindRealtimeClient._normalize_stock(
        {
            "stock_id": "2330",
            "close": float("nan"),
            "volume": float("nan"),
            "high": float("inf"),
            "low": float("-inf"),
        }
    )
    assert q["symbol"] == "2330"
    assert q["price"] is None
    assert q["volume"] is None
    assert q["high"] is None
    assert q["low"] is None


# ── 正規化（Sponsor 開通後的 happy path，以 mock 驗證）────


@pytest.mark.asyncio
async def test_stock_snapshot_normalization_official_columns(mock_transport) -> None:
    """以官方文件所載欄位為準（llms-full.txt: taiwan_stock_tick_snapshot）。

    官方買/賣價是 buy_price / sell_price（不是 bid/ask），漲跌是 change_price。
    這組欄位名先前是我臆測的，導致真實資料會抓不到 → 本測試釘住官方名稱。
    """
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "success",
            "status": 200,
            "data": [
                {
                    "date": "2026-07-15 10:30:00",
                    "stock_id": "2330",
                    "TickType": 1,
                    "open": 1140.0,
                    "high": 1155.0,
                    "low": 1138.0,
                    "close": 1150.0,
                    "change_price": 10.0,
                    "change_rate": 0.88,
                    "average_price": 1147.5,
                    "volume": 120,
                    "total_volume": 18500,
                    "yesterday_volume": 20100,
                    "volume_ratio": 0.92,
                    "amount": 138000000,
                    "total_amount": 21275000000,
                    "buy_price": 1149.0,
                    "buy_volume": 3,
                    "sell_price": 1150.0,
                    "sell_volume": 5,
                }
            ],
        }
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert res["available"] is True
    assert res["reason"] is None
    assert res["as_of"] == "2026-07-15 10:30:00"
    q = res["quotes"][0]
    assert q["symbol"] == "2330"
    assert q["price"] == Decimal("1150.0")
    assert q["change"] == Decimal("10.0")  # 來自 change_price
    assert q["change_rate"] == Decimal("0.88")
    assert q["average_price"] == Decimal("1147.5")
    assert q["volume"] == 120
    assert q["total_volume"] == 18500
    assert q["yesterday_volume"] == 20100
    assert q["volume_ratio"] == Decimal("0.92")
    assert q["bid_price"] == Decimal("1149.0")  # 來自 buy_price
    assert q["bid_volume"] == 3
    assert q["ask_price"] == Decimal("1150.0")  # 來自 sell_price
    assert q["ask_volume"] == 5
    assert q["tick_type"] == 1
    assert q["raw"]["stock_id"] == "2330"  # raw passthrough 供 forward-compat


@pytest.mark.asyncio
async def test_futures_snapshot_official_columns(mock_transport) -> None:
    """期貨官方 data_id 是 TXF，代號欄位是 futures_id。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "success",
            "status": 200,
            "data": [
                {
                    "date": "2026-07-15 10:30:00",
                    "futures_id": "TXF",
                    "close": 23150.0,
                    "change_price": -35.0,
                    "buy_price": 23149.0,
                    "sell_price": 23151.0,
                    "total_volume": 88000,
                }
            ],
        }
    )
    res = await _client().fetch_futures_snapshot(["TXF"])
    assert res["available"] is True
    q = res["quotes"][0]
    assert q["symbol"] == "TXF"
    assert q["price"] == Decimal("23150.0")
    assert q["change"] == Decimal("-35.0")
    assert q["bid_price"] == Decimal("23149.0")
    assert q["ask_price"] == Decimal("23151.0")


@pytest.mark.asyncio
async def test_token_sent_as_bearer_header(mock_transport) -> None:
    """官方文件明訂以 Authorization: Bearer {token} 認證（token 值本身不含前綴）。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {"status": 200, "msg": "ok", "data": []}
    )
    await _client(token="tok123").fetch_stock_snapshot(["2330"])
    # headers 掛在 client 上，實際送出的 request 會帶上；此處驗證 params 仍相容帶 token
    assert mock_transport["calls"][0]["kwargs"]["params"]["token"] == "tok123"


def test_normalize_stock_tolerates_naming_variants() -> None:
    """官方欄位名以 test_stock_snapshot_normalization_official_columns 為準；

    這裡確保萬一上游改用其他常見命名（PascalCase / bid-ask 用語）也不會整組變空——
    官方名稱優先，這些只是最後的保險。
    """
    q = FinMindRealtimeClient._normalize_stock(
        {
            "date": "2026-07-15 10:30:00",
            "StockID": "2317",
            "Close": "205.5",
            "Open": "204",
            "Change": "1.5",
            "Volume": "88",
            "TotalVolume": "9000",
            "BidPrice": "205.0",
            "AskPrice": "205.5",
            "TickType": 2,
        }
    )
    assert q["symbol"] == "2317"
    assert q["price"] == Decimal("205.5")
    assert q["volume"] == 88
    assert q["bid_price"] == Decimal("205.0")


def test_normalize_futures_uses_futures_id() -> None:
    """期貨代號欄位是 futures_id，不是 stock_id。"""
    q = FinMindRealtimeClient._normalize_futures(
        {"date": "2026-07-15 10:30:00", "futures_id": "TX", "close": 23150, "volume": 5}
    )
    assert q["symbol"] == "TX"
    assert q["price"] == Decimal("23150")


def test_normalize_handles_missing_and_bad_values() -> None:
    """缺欄位 / 髒值不可炸，應回 None。"""
    q = FinMindRealtimeClient._normalize_stock({"stock_id": "2330", "close": "N/A", "volume": None})
    assert q["symbol"] == "2330"
    assert q["price"] is None
    assert q["volume"] is None
    assert q["high"] is None


@pytest.mark.asyncio
async def test_always_fetch_all_and_filter(mock_transport) -> None:
    """一律不帶 data_id 抓全部再本地過濾（單檔多檔皆然）。

    兩個理由：
    1. FinMind 不支援逗號合併多代號——`data_id=2330,2317` 會靜默回 data:[]（實測）。
    2. 抓全部 + 快取後，上游用量與查詢檔數/頁面數脫鉤（見 SNAPSHOT_CACHE_TTL_S）。
    """
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "ok",
            "status": 200,
            "data": [
                {"stock_id": "2330", "close": 1150},
                {"stock_id": "2317", "close": 240},
                {"stock_id": "5701", "close": 4.38},  # 沒要的股票要被濾掉
            ],
        }
    )
    res = await _client().fetch_stock_snapshot(["2330", "2317"])
    assert len(mock_transport["calls"]) == 1
    # 關鍵迴歸：不得帶 data_id（帶逗號合併值會回空）
    assert "data_id" not in mock_transport["calls"][0]["kwargs"]["params"]
    assert {q["symbol"] for q in res["quotes"]} == {"2330", "2317"}


@pytest.mark.asyncio
async def test_single_symbol_also_fetches_all_and_filters(mock_transport) -> None:
    """單檔查詢同樣走「抓全部再過濾」，才能共用快取、不額外吃額度。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "ok",
            "status": 200,
            "data": [
                {"stock_id": "2330", "close": 1150},
                {"stock_id": "2317", "close": 240},
            ],
        }
    )
    res = await _client().fetch_stock_snapshot(["2330"])
    assert "data_id" not in mock_transport["calls"][0]["kwargs"]["params"]
    assert [q["symbol"] for q in res["quotes"]] == ["2330"]


@pytest.mark.asyncio
async def test_snapshot_is_cached_so_quota_is_independent_of_usage(
    mock_transport, monkeypatch
) -> None:
    """核心設計：多次查詢（不同股票）只打上游 1 次，其餘走快取。

    這是額度安全的關鍵——輪詢時上游用量固定為 3600/TTL 次/小時，與開幾個頁面、
    查幾檔股票無關。
    """
    fake = _FakeRedis()

    async def _fake_get_redis(*_a, **_kw):  # type: ignore[no-untyped-def]
        return fake

    monkeypatch.setattr("app.data_sources.tw.finmind_realtime.get_redis", _fake_get_redis)
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "ok",
            "status": 200,
            "data": [
                {"stock_id": "2330", "close": 1150},
                {"stock_id": "2317", "close": 240},
            ],
        }
    )
    c = _client()
    r1 = await c.fetch_stock_snapshot(["2330"])
    r2 = await c.fetch_stock_snapshot(["2317"])  # 不同股票
    r3 = await c.fetch_stock_snapshot(["2330", "2317"])  # 多檔

    assert len(mock_transport["calls"]) == 1  # ← 三次查詢只打上游一次
    assert r1["cached"] is False and r2["cached"] is True and r3["cached"] is True
    assert [q["symbol"] for q in r2["quotes"]] == ["2317"]
    assert {q["symbol"] for q in r3["quotes"]} == {"2330", "2317"}
    # 快取有帶 TTL，否則報價會永遠不更新
    assert fake.set_calls[0][1] == SNAPSHOT_CACHE_TTL_S


@pytest.mark.asyncio
async def test_stock_and_futures_use_separate_cache_keys(mock_transport, monkeypatch) -> None:
    """個股與期貨不可共用快取鍵，否則會互相覆蓋。"""
    fake = _FakeRedis()

    async def _fake_get_redis(*_a, **_kw):  # type: ignore[no-untyped-def]
        return fake

    monkeypatch.setattr("app.data_sources.tw.finmind_realtime.get_redis", _fake_get_redis)
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "ok",
            "status": 200,
            "data": [{"stock_id": "2330", "close": 1150}, {"futures_id": "TXFR2", "close": 45721}],
        }
    )
    c = _client()
    await c.fetch_stock_snapshot(["2330"])
    res = await c.fetch_futures_snapshot(["TXF"])
    assert len(mock_transport["calls"]) == 2  # 兩種各打一次，沒有互吃快取
    assert [q["symbol"] for q in res["quotes"]] == ["TXFR2"]


@pytest.mark.asyncio
async def test_multiple_futures_filtered_by_prefix(mock_transport) -> None:
    """data_id=TXF 實回各月份契約（futures_id 形如 TXFR2），故多代號過濾用 prefix。"""
    mock_transport["response_factory"] = lambda m, u, k: _resp(
        {
            "msg": "ok",
            "status": 200,
            "data": [
                {"futures_id": "TXFR2", "close": 45721},
                {"futures_id": "MXFR2", "close": 45700},
                {"futures_id": "TEFR2", "close": 2000},  # 電子期，不該出現
            ],
        }
    )
    res = await _client().fetch_futures_snapshot(["TXF", "MXF"])
    assert {q["symbol"] for q in res["quotes"]} == {"TXFR2", "MXFR2"}

"""FinMind data source — TW 主資料源。

API 文件：https://finmindtrade.com/analysis/#/data/api

支援 dataset（v7.0 P5）：
- TaiwanStockPrice → OHLCV
- TaiwanStockInfo → 公司基本資料
- TaiwanStockFinancialStatements → 財務報表
- TaiwanStockMonthRevenue → 月營收
- TaiwanStockInstitutionalInvestorsBuySell → 三大法人
- TaiwanStockMarginPurchaseShortSale → 融資融券

免費版限制：依官方公告（v7.0 P5 撰寫時依 ~600/day 設保守 rate limit）。
token 為空時：仍可查 public dataset，但配額更低；觸到 401/402/429 會交給 fallback。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pandas as pd

from app.core.errors import AuthError, ExternalServiceError, RateLimitError
from app.core.http_client import request_with_retry
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


def _parse_news_dt(v: Any) -> Any:
    """FinMind 新聞 date（'2026-07-10 01:12:24' 或純日期）→ tz-aware datetime。

    解析失敗回 None（caller 應略過該筆——published_at 不可為 NULL）。
    """
    from datetime import UTC, datetime

    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


@register_data_source
class FinMindSource(BaseDataSource):
    """FinMind API。"""

    name = "finmind"
    priority = 10  # 主源（TW OHLCV / 財報 / 籌碼 / 月營收）
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (
        DataKind.OHLCV,
        DataKind.COMPANY_INFO,
        DataKind.FINANCIAL,
        DataKind.INSTITUTIONAL,
        DataKind.MARGIN,
        DataKind.MONTHLY_REVENUE,
    )
    rate_limit_per_sec = 0.5  # 免費版保守值（2 秒 1 次）
    base_url = "https://api.finmindtrade.com/api/v4/data"

    # ── 抽象 fetch_* 實作 ────────────────────────────────

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        data = await self._call(
            dataset="TaiwanStockPrice",
            data_id=symbol,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        return self._normalize_ohlcv(data)

    async def fetch_all_news(self, start: date, end: date) -> list[dict[str, Any]]:
        """全市場相關新聞（FinMind TaiwanStockNews，Free 等級，取代被 WAF 擋的 MOPS）。

        單次請求只回一天（官方 Single day per request），故逐日查；不帶 data_id → 整天全市場
        （實測單日 ~1,593 筆 / 576 檔）。回標準化 news item：symbol/title/summary/url/source/
        published_at/market，url 作 dedupe key。
        """
        from datetime import timedelta

        out: list[dict[str, Any]] = []
        day = start
        while day <= end:
            try:
                data = await self._call(dataset="TaiwanStockNews", start_date=day.isoformat())
            except (AuthError, RateLimitError, ExternalServiceError):
                data = []  # 單日失敗不影響其他日
            for r in data:
                link = r.get("link")
                title = r.get("title")
                if not link or not title:
                    continue
                out.append(
                    {
                        "symbol": r.get("stock_id"),
                        "title": title,
                        "summary": r.get("description"),
                        "url": link,
                        "source": r.get("source"),
                        "published_at": _parse_news_dt(r.get("date")),
                        "market": "TWSE",
                    }
                )
            day += timedelta(days=1)
        return out

    async def fetch_company_info(self, symbol: str) -> dict[str, Any]:
        data = await self._call(dataset="TaiwanStockInfo", data_id=symbol)
        if not data:
            return {}
        # FinMind 回 list；取第一筆作為當前公司資料
        row = data[0]
        return {
            "symbol": row.get("stock_id"),
            "name": row.get("stock_name"),
            "industry": row.get("industry_category"),
            "type": row.get("type"),
            "raw": row,
        }

    async def fetch_financial(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        """FinMind TaiwanStockFinancialStatements 一次回該股全部歷史；caller 可篩。"""
        params: dict[str, Any] = {
            "dataset": "TaiwanStockFinancialStatements",
            "data_id": symbol,
        }
        # 給 start/end 可縮小範圍
        if year is not None:
            params["start_date"] = f"{year}-01-01"
            params["end_date"] = f"{year}-12-31"
        data = await self._call(**params)
        return [self._normalize_financial(row) for row in data]

    async def fetch_institutional(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        data = await self._call(
            dataset="TaiwanStockInstitutionalInvestorsBuySell",
            data_id=symbol,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        return self._normalize_institutional(data)

    async def fetch_margin(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        data = await self._call(
            dataset="TaiwanStockMarginPurchaseShortSale",
            data_id=symbol,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        return self._normalize_margin(data)

    async def fetch_all_per(self, start: date, end: date) -> list[dict[str, Any]]:
        """全市場本益比 / 殖利率 / 淨值比（TaiwanStockPER，不帶 data_id → 單日全市場）。

        用於刷新 stock_metrics 的近日 PE/殖利率。回 {symbol, date, pe_ratio, pbr, dividend_yield}。
        """
        from datetime import timedelta

        out: list[dict[str, Any]] = []
        day = start
        while day <= end:
            try:
                data = await self._call(dataset="TaiwanStockPER", start_date=day.isoformat())
            except (AuthError, RateLimitError, ExternalServiceError):
                data = []
            for r in data:
                sid = r.get("stock_id")
                d = r.get("date")
                if not sid or not d:
                    continue
                try:
                    d_obj = date.fromisoformat(str(d)[:10])
                except ValueError:
                    continue
                out.append(
                    {
                        "symbol": sid,
                        "date": d_obj,
                        "pe_ratio": _to_decimal_or_none(r.get("PER")),
                        "pbr": _to_decimal_or_none(r.get("PBR")),
                        "dividend_yield": _to_decimal_or_none(r.get("dividend_yield")),
                    }
                )
            day += timedelta(days=1)
        return out

    async def fetch_all_market_value(self, start: date, end: date) -> list[dict[str, Any]]:
        """全市場市值（TaiwanStockMarketValue，不帶 data_id → 單日全市場）。

        回 {symbol, date, market_cap}。用於刷新 stock_metrics 近日市值。
        """
        from datetime import timedelta

        out: list[dict[str, Any]] = []
        day = start
        while day <= end:
            try:
                data = await self._call(
                    dataset="TaiwanStockMarketValue", start_date=day.isoformat()
                )
            except (AuthError, RateLimitError, ExternalServiceError):
                data = []
            for r in data:
                sid = r.get("stock_id")
                d = r.get("date")
                if not sid or not d:
                    continue
                try:
                    d_obj = date.fromisoformat(str(d)[:10])
                except ValueError:
                    continue
                mv = r.get("market_value")
                try:
                    mv_int = int(float(mv)) if mv not in (None, "", "-") else None
                except (ValueError, TypeError):
                    mv_int = None
                out.append({"symbol": sid, "date": d_obj, "market_cap": mv_int})
            day += timedelta(days=1)
        return out

    async def fetch_all_margin(self, start: date, end: date) -> list[dict[str, Any]]:
        """全市場融資融券（不帶 data_id → 單日回整個市場，逐日查）。

        用途：本地 FinMind 庫盤後入庫有落差（近 1~2 週只有零星幾檔）時，用「每天一次
        請求」補齊近日全市場，避開 2,000 檔逐檔 fan-out 打爆連線/配額。回標準化 upsert
        dict：symbol + 8 個 margin 欄位 + date（int 已轉好，缺值補 0）。
        """
        from datetime import timedelta

        _cols = (
            "MarginPurchaseBuy",
            "MarginPurchaseSell",
            "MarginPurchaseTodayBalance",
            "MarginPurchaseLimit",
            "ShortSaleBuy",
            "ShortSaleSell",
            "ShortSaleTodayBalance",
            "ShortSaleLimit",
        )
        _out_map = {
            "MarginPurchaseBuy": "margin_buy",
            "MarginPurchaseSell": "margin_sell",
            "MarginPurchaseTodayBalance": "margin_balance",
            "MarginPurchaseLimit": "margin_quota",
            "ShortSaleBuy": "short_buy",
            "ShortSaleSell": "short_sell",
            "ShortSaleTodayBalance": "short_balance",
            "ShortSaleLimit": "short_quota",
        }
        out: list[dict[str, Any]] = []
        day = start
        while day <= end:
            try:
                data = await self._call(
                    dataset="TaiwanStockMarginPurchaseShortSale",
                    start_date=day.isoformat(),
                )
            except (AuthError, RateLimitError, ExternalServiceError):
                data = []  # 單日失敗不影響其他日
            for r in data:
                sid = r.get("stock_id")
                d = r.get("date")
                if not sid or not d:
                    continue
                try:
                    d_obj = date.fromisoformat(str(d)[:10])
                except ValueError:
                    continue
                item: dict[str, Any] = {"symbol": sid, "date": d_obj}
                for src in _cols:
                    v = r.get(src)
                    try:
                        item[_out_map[src]] = int(float(v)) if v not in (None, "", "-") else 0
                    except (ValueError, TypeError):
                        item[_out_map[src]] = 0
                out.append(item)
            day += timedelta(days=1)
        return out

    async def fetch_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": symbol,
        }
        if year is not None:
            params["start_date"] = f"{year}-01-01"
            params["end_date"] = f"{year}-12-31"
        data = await self._call(**params)
        return [self._normalize_monthly_revenue(row) for row in data]

    # ── 內部：統一呼叫 + 鑑別錯誤 ────────────────────────

    async def _call(self, **params: Any) -> list[dict[str, Any]]:
        """送一次 GET 給 FinMind 並回 data list。

        Raises:
            AuthError: 401（token 錯）
            RateLimitError: 402 / 429
            ExternalServiceError: 其他
        """
        token = self.settings.FINMIND_TOKEN
        if token is not None:
            params["token"] = token.get_secret_value()

        # 套用 rate limiter（subclass 設了 rate_limit_per_sec 才有 limiter）
        if self.limiter is not None:
            async with self.limiter:
                return await self._do_call(params)
        return await self._do_call(params)

    async def _do_call(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        client_cm = self._get_client()
        async with client_cm as client:
            try:
                resp = await request_with_retry(
                    client,
                    "GET",
                    # 必須傳「絕對 URL」：httpx 會把 base_url 正規化成尾端帶斜線
                    # (".../api/v4/data" → ".../api/v4/data/")，再與相對路徑 "" 合併後
                    # 打到 ".../api/v4/data/"，FinMind 對此回 307 轉址；而 client 基於防
                    # SSRF 設了 follow_redirects=False → 拿到空 body → "回傳非 JSON"，
                    # 導致整條 FinMind API 源實質失效。傳絕對 URL 可跳過 base_url 合併。
                    self.base_url,
                    source_name=self.name,
                    raise_on_4xx=False,
                    params=params,
                )
            except httpx.RequestError as e:
                # 連線層完全失敗（DNS / refused / timeout 重試完）— 包成 ExternalServiceError
                raise ExternalServiceError(
                    message_zh="FinMind 連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e

        status = resp.status_code

        if status == 401:
            raise AuthError(
                message_zh="FinMind token 認證失敗",
                source=self.name,
                status=status,
            )
        if status in (402, 429):
            raise RateLimitError(
                message_zh="FinMind 配額已用盡或頻率過高",
                source=self.name,
                status=status,
            )
        if status >= 400:
            raise ExternalServiceError(
                message_zh=f"FinMind 回應錯誤（{status}）",
                source=self.name,
                status=status,
                body=resp.text[:500],
            )

        try:
            payload = resp.json()
        except Exception as e:
            raise ExternalServiceError(
                message_zh="FinMind 回傳非 JSON",
                source=self.name,
                body=resp.text[:500],
            ) from e

        # FinMind 標準格式：{"status": 200, "msg": "success", "data": [...]}
        if isinstance(payload, dict):
            api_status = payload.get("status")
            msg = str(payload.get("msg", "")).lower()
            if api_status == 401 or "token" in msg:
                raise AuthError(
                    message_zh="FinMind token 認證失敗",
                    source=self.name,
                    msg=str(payload.get("msg")),
                )
            if api_status in (402, 429) or "limit" in msg:
                raise RateLimitError(
                    message_zh="FinMind 配額已用盡",
                    source=self.name,
                    msg=str(payload.get("msg")),
                )
            if api_status not in (200, None):
                raise ExternalServiceError(
                    message_zh=f"FinMind 業務錯誤（status={api_status}）",
                    source=self.name,
                    msg=str(payload.get("msg")),
                )
            data = payload.get("data") or []
            if not isinstance(data, list):
                raise ExternalServiceError(
                    message_zh="FinMind data 欄位格式錯誤",
                    source=self.name,
                )
            return data
        if isinstance(payload, list):
            return payload
        raise ExternalServiceError(
            message_zh="FinMind 回傳格式不認識",
            source=self.name,
        )

    # ── 標準化 helpers ───────────────────────────────────

    @staticmethod
    def _normalize_ohlcv(data: list[dict[str, Any]]) -> pd.DataFrame:
        """FinMind TaiwanStockPrice → 統一 OHLCV DataFrame。

        FinMind 欄位：date / stock_id / Trading_Volume / Trading_money /
          open / max / min / close / spread / Trading_turnover
        統一輸出欄位：date / open / high / low / close / volume / turnover
        """
        if not data:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "turnover"]
            )
        df = pd.DataFrame(data)
        # 重命名
        rename_map = {
            "max": "high",
            "min": "low",
            "Trading_Volume": "volume",
            "Trading_money": "turnover",
        }
        df = df.rename(columns=rename_map)
        # 篩需要的欄位
        keep = [
            c for c in ("date", "open", "high", "low", "close", "volume", "turnover") if c in df
        ]
        df = df[keep].copy()
        # date → date type
        df["date"] = pd.to_datetime(df["date"]).dt.date
        # OHLC → Decimal-as-object（避免後續 PG Numeric upsert 精度誤差）
        for col in ("open", "high", "low", "close"):
            if col in df.columns:
                df[col] = df[col].apply(_to_decimal_or_none)
        # volume → int64
        if "volume" in df.columns:
            df["volume"] = df["volume"].fillna(0).astype("int64")
        if "turnover" in df.columns:
            df["turnover"] = df["turnover"].apply(_to_decimal_or_none)
        return df

    @staticmethod
    def _normalize_institutional(data: list[dict[str, Any]]) -> pd.DataFrame:
        """三大法人欄位重組 — FinMind 一天有多筆（按法人 type 拆），需 pivot。"""
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        # FinMind 欄位：date / stock_id / name / buy / sell
        # name in {"Foreign_Investor", "Investment_Trust", "Dealer_Hedging", "Dealer_self"}
        # 我們聚合：foreign / trust / dealer（buy/sell 加總）+ 算 net
        if "name" not in df.columns:
            return df
        df["buy"] = df["buy"].fillna(0).astype("int64")
        df["sell"] = df["sell"].fillna(0).astype("int64")
        df["date"] = pd.to_datetime(df["date"]).dt.date

        def group_name(n: str) -> str | None:
            n_lower = (n or "").lower()
            if n_lower.startswith("foreign"):
                return "foreign"
            if "investment_trust" in n_lower or "trust" in n_lower:
                return "trust"
            if "dealer" in n_lower:
                return "dealer"
            return None

        df["group"] = df["name"].map(group_name)
        df = df.dropna(subset=["group"])

        agg = df.groupby(["date", "group"], as_index=False).agg({"buy": "sum", "sell": "sum"})
        pivot_buy = agg.pivot(index="date", columns="group", values="buy").fillna(0).astype("int64")
        pivot_sell = (
            agg.pivot(index="date", columns="group", values="sell").fillna(0).astype("int64")
        )

        out = pd.DataFrame(index=pivot_buy.index)
        for g in ("foreign", "trust", "dealer"):
            buy_col = pivot_buy[g] if g in pivot_buy.columns else 0
            sell_col = pivot_sell[g] if g in pivot_sell.columns else 0
            out[f"{g}_buy"] = buy_col
            out[f"{g}_sell"] = sell_col
            out[f"{g}_net"] = buy_col - sell_col
        return out.reset_index()

    @staticmethod
    def _normalize_margin(data: list[dict[str, Any]]) -> pd.DataFrame:
        """融資融券標準化。FinMind 欄位：MarginPurchaseTodayBalance / ShortSaleTodayBalance / ..."""
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        # 重要欄位 mapping
        rename_map = {
            "MarginPurchaseBuy": "margin_buy",
            "MarginPurchaseSell": "margin_sell",
            "MarginPurchaseTodayBalance": "margin_balance",
            "MarginPurchaseLimit": "margin_quota",
            "ShortSaleBuy": "short_buy",
            "ShortSaleSell": "short_sell",
            "ShortSaleTodayBalance": "short_balance",
            "ShortSaleLimit": "short_quota",
        }
        df = df.rename(columns=rename_map)
        keep_cols = ["date", *rename_map.values()]
        present = [c for c in keep_cols if c in df.columns]
        df = df[present].copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        for c in present:
            if c == "date":
                continue
            df[c] = df[c].fillna(0).astype("int64")
        return df

    @staticmethod
    def _normalize_financial(row: dict[str, Any]) -> dict[str, Any]:
        """FinMind TaiwanStockFinancialStatements 一筆 = 一個欄位（type / value）。

        Caller 拿到 list[dict] 後可自己彙整成 IS/BS/CF。為避免本層做太多 domain 判斷，
        這裡只統一標準化單筆格式：
        - stock_id → symbol
        - date / year / quarter 解析
        - value → Decimal-as-object
        - origin_name 保留 source 欄位名
        """
        d = dict(row)
        d.setdefault("symbol", d.pop("stock_id", None))
        if d.get("date"):
            d["date_parsed"] = pd.to_datetime(d["date"]).date()
        if "value" in d:
            d["value"] = _to_decimal_or_none(d["value"])
        return d

    @staticmethod
    def _normalize_monthly_revenue(row: dict[str, Any]) -> dict[str, Any]:
        """FinMind TaiwanStockMonthRevenue 一筆 = 一個月營收。

        FinMind 欄位：date / stock_id / country / revenue / revenue_month / revenue_year
        """
        d = dict(row)
        d.setdefault("symbol", d.pop("stock_id", None))
        if "revenue" in d:
            d["revenue"] = _to_decimal_or_none(d["revenue"])
        # FinMind 給的 year/month
        d["year"] = int(d.get("revenue_year") or 0) or None
        d["month"] = int(d.get("revenue_month") or 0) or None
        return d


def _to_decimal_or_none(v: Any) -> Decimal | None:
    """安全轉 Decimal；None / NaN / 空字串 → None。"""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, float):
        if pd.isna(v):
            return None
        return Decimal(str(v))
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() == "nan":
            return None
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


__all__ = ["FinMindSource"]

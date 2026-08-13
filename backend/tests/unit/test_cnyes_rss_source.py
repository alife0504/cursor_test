"""cnyes RSS source 單元測試（含 feedparser parsing）。"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.data_sources.tw.cnyes_rss_source import CnyesRSSSource

pytestmark = pytest.mark.unit


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>鉅亨網台股新聞</title>
<item>
  <title>台積電 2330 法說會：營收創新高</title>
  <link>https://news.cnyes.com/news/id/1111</link>
  <description>本公司今日召開法說會，營收創新高。</description>
  <pubDate>Mon, 12 May 2026 08:00:00 GMT</pubDate>
</item>
<item>
  <title>鴻海 2317 智慧電動車布局加速</title>
  <link>https://news.cnyes.com/news/id/2222</link>
  <description>2317 鴻海宣布加速電動車布局。</description>
  <pubDate>Sun, 11 May 2026 06:00:00 GMT</pubDate>
</item>
<item>
  <title>大盤週報：加權指數收漲</title>
  <link>https://news.cnyes.com/news/id/3333</link>
  <description>加權指數本週收漲 1%。</description>
  <pubDate>Sat, 10 May 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""


@pytest.fixture
def cnyes() -> CnyesRSSSource:
    CIRCUIT_BREAKERS.pop("cnyes_rss", None)
    src = CnyesRSSSource(settings)
    src.limiter = None  # 測試中跳過 rate limit
    return src


@pytest.fixture
def mock_get(monkeypatch):  # type: ignore[no-untyped-def]
    state = {"response_factory": None}

    async def fake_get(self, url, **kwargs):  # type: ignore[no-untyped-def]
        return state["response_factory"](url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return state


def _rss_response(status: int, body: str) -> httpx.Response:
    req = httpx.Request("GET", "https://news.cnyes.com/rss/cat/tw_stock")
    return httpx.Response(status_code=status, request=req, text=body)


@pytest.mark.asyncio
async def test_fetch_news_no_symbol_returns_all(cnyes: CnyesRSSSource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _rss_response(200, SAMPLE_RSS)
    out = await cnyes.fetch_news(symbol=None)
    assert len(out) == 3
    assert all("title" in n for n in out)
    assert all(n["url"].startswith("https://news.cnyes.com/") for n in out)


@pytest.mark.asyncio
async def test_fetch_news_filters_by_symbol(cnyes: CnyesRSSSource, mock_get) -> None:
    """symbol='2330' 應只回標題或內文含 2330 的新聞。"""
    mock_get["response_factory"] = lambda url, kw: _rss_response(200, SAMPLE_RSS)
    out = await cnyes.fetch_news(symbol="2330")
    assert len(out) == 1
    assert "2330" in out[0]["title"]


@pytest.mark.asyncio
async def test_fetch_news_filters_by_since(cnyes: CnyesRSSSource, mock_get) -> None:
    """since=2026-05-11 應排除 2026-05-10 的新聞。"""
    mock_get["response_factory"] = lambda url, kw: _rss_response(200, SAMPLE_RSS)
    out = await cnyes.fetch_news(symbol=None, since=date(2026, 5, 11))
    assert len(out) == 2
    assert all(n["published_at"].date() >= date(2026, 5, 11) for n in out)


@pytest.mark.asyncio
async def test_fetch_news_http_error_raises(cnyes: CnyesRSSSource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _rss_response(503, "")
    with pytest.raises(ExternalServiceError):
        await cnyes.fetch_news(symbol="2330")

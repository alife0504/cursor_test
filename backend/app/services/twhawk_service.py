"""tw-hawk / twofc 本地資料湖（DuckDB, 唯讀）讀取服務 — 重大公告 + 每日情緒。

沿用 market_service 讀 twofc 的既有模式：
- TWHAWK_ENABLED gate；duckdb.connect(read_only=True) 於 asyncio.to_thread（阻塞→執行緒）。
- 讀不到（未掛載/被鎖/未啟用）一律 graceful 回空，不影響頁面其餘。
- tw-hawk 為唯讀外部資料湖，只讀不寫。

重大公告（twofc_events）：MOPS 重大訊息類，**含真實 announced_at（公告日）**，PIT 正確
（解決我方 announcements.announced_at 全 NULL 的偷看未來問題）。
每日情緒（twofc_sentiment_daily）：每日情緒分數 + AI 摘要 + 討論熱度（聚合日度訊號）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# 視為「重大公告」的事件類型（MOPS 重大訊息；排除純交易狀態如 margin_suspended/trading_halt）
_MATERIAL_EVENT_TYPES = (
    "board_resolution",
    "material_other",
    "dividend_decision",
    "dividend_schedule",
    "asset_disposal",
    "capital_increase",
    "exec_change",
    "endorsement_guarantee",
    "subsidiary_notice",
    "earnings_call",
    "shareholder_meeting",
)


class TwhawkService:
    """讀 twofc.duckdb 的重大公告與每日情緒（唯讀、graceful）。"""

    def _enabled(self) -> bool:
        return bool(getattr(settings, "TWHAWK_ENABLED", False))

    async def get_material_events(self, symbol: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """個股重大公告（twofc_events，PIT：只回已公告 announced_at<=now）。"""
        if not self._enabled():
            return []
        path = settings.TWHAWK_DUCKDB_PATH
        now = datetime.now(tz=UTC)
        types = set(_MATERIAL_EVENT_TYPES)

        def _read() -> list[dict[str, Any]]:
            import duckdb

            con = duckdb.connect(path, read_only=True)
            try:
                # 靜態 SQL（PIT：只取已公告）；event_type 過濾在 Python（避免動態組 IN）
                rows = con.execute(
                    "SELECT event_type, event_subtype, event_date, announced_at, "
                    "severity, direction, payload FROM twofc_events "
                    "WHERE stock_id = ? AND announced_at IS NOT NULL AND announced_at <= ? "
                    "ORDER BY announced_at DESC",
                    [symbol, now],
                ).fetchall()
                out = []
                for r in rows:
                    if r[0] not in types:
                        continue
                    out.append(
                        {
                            "event_type": r[0],
                            "event_subtype": r[1],
                            "event_date": str(r[2])[:10] if r[2] else None,
                            "announced_at": r[3].isoformat() if r[3] else None,
                            "severity": r[4],
                            "direction": r[5],
                            "payload": r[6],
                        }
                    )
                    if len(out) >= int(limit):
                        break
                return out
            finally:
                con.close()

        try:
            raw = await asyncio.to_thread(_read)
        except Exception as exc:
            logger.warning("twhawk.material_events.read_failed symbol=%s error=%s", symbol, exc)
            return []

        out: list[dict[str, Any]] = []
        for r in raw:
            subject = None
            if r.get("payload"):
                try:
                    subject = (json.loads(r["payload"]) or {}).get("subject")
                except (ValueError, TypeError):
                    subject = None
            out.append(
                {
                    "event_type": r["event_type"],
                    "event_subtype": r["event_subtype"],
                    "title": subject or r["event_type"],
                    "event_date": r["event_date"],
                    "announced_at": r["announced_at"],
                    "severity": r["severity"],
                    "direction": r["direction"],
                }
            )
        return out

    async def get_daily_sentiment(self, symbol: str, *, days: int = 30) -> list[dict[str, Any]]:
        """個股每日情緒（twofc_sentiment_daily，近 N 天）。"""
        if not self._enabled():
            return []
        path = settings.TWHAWK_DUCKDB_PATH
        since = (datetime.now(tz=UTC).date() - timedelta(days=days)).isoformat()

        def _read() -> list[dict[str, Any]]:
            import duckdb

            con = duckdb.connect(path, read_only=True)
            try:
                rows = con.execute(
                    """
                    SELECT date, sentiment_score, discussion_volume, volume_spike_z,
                           attention_gap, short_summary
                    FROM twofc_sentiment_daily
                    WHERE stock_id = ? AND date >= ?
                    ORDER BY date DESC
                    """,
                    [symbol, since],
                ).fetchall()
                return [
                    {
                        "date": str(r[0])[:10],
                        "sentiment_score": float(r[1]) if r[1] is not None else None,
                        "discussion_volume": int(r[2]) if r[2] is not None else None,
                        "volume_spike_z": float(r[3]) if r[3] is not None else None,
                        "attention_gap": float(r[4]) if r[4] is not None else None,
                        "short_summary": r[5],
                    }
                    for r in rows
                ]
            finally:
                con.close()

        try:
            return await asyncio.to_thread(_read)
        except Exception as exc:
            logger.warning("twhawk.sentiment.read_failed symbol=%s error=%s", symbol, exc)
            return []


__all__ = ["TwhawkService"]

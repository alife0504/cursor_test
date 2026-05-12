"""NewsRepository — news_metadata CRUD。

依 PLAN.md 第 ADR-002（向量分離儲存 — 向量在 Qdrant，元資料在 PG）。

P5 範圍：
- list_by_symbol(symbol, since, limit)
- upsert_many_by_url(items): URL 作為自然 dedupe key
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.logging_config import get_logger
from app.models.news import NewsMetadata
from app.repos.base import BaseRepository

logger = get_logger(__name__)


class NewsRepository(BaseRepository):
    async def list_by_symbol(
        self,
        symbol: str | None,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsMetadata]:
        stmt = select(NewsMetadata)
        if symbol is not None:
            stmt = stmt.where(NewsMetadata.symbol == symbol)
        if since is not None:
            stmt = stmt.where(NewsMetadata.published_at >= since)
        stmt = stmt.order_by(NewsMetadata.published_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_many_by_url(self, items: list[dict[str, Any]], *, commit: bool = False) -> int:
        """以 url 為自然 dedupe key — 同 url 視為同一則新聞。

        因 news_metadata 沒有 url unique constraint（vector point id 在 Qdrant），
        本方法以「查 url 是否存在 → 不存在才 insert」做去重。
        若 caller 想嚴格 atomic，可在 P6 改加 unique index。

        Returns: 新增筆數（已存在不重複 insert）。
        """
        if not items:
            return 0

        # 先查現有 URL（避免 N+1，批次查一次）
        urls = [it.get("url") for it in items if it.get("url")]
        existing_urls: set[str] = set()
        if urls:
            stmt = select(NewsMetadata.url).where(NewsMetadata.url.in_(urls))
            result = await self.session.execute(stmt)
            existing_urls = {row[0] for row in result.all() if row[0]}

        inserted = 0
        for raw in items:
            url = raw.get("url")
            if url and url in existing_urls:
                continue
            entry = NewsMetadata(
                id=raw.get("id") or uuid.uuid4(),
                symbol=raw.get("symbol"),
                market=raw.get("market"),
                title=raw.get("title", ""),
                summary=raw.get("summary"),
                source=raw.get("source"),
                url=url,
                author=raw.get("author"),
                published_at=raw.get("published_at"),
                sentiment=raw.get("sentiment", "unknown"),
                sentiment_score=raw.get("sentiment_score"),
                qdrant_collection=raw.get("qdrant_collection"),
                qdrant_point_id=raw.get("qdrant_point_id"),
                word_count=raw.get("word_count"),
                extra_meta=raw.get("extra_meta"),
            )
            self.session.add(entry)
            inserted += 1
            if url:
                existing_urls.add(url)
        if commit:
            await self.session.commit()
        return inserted


__all__ = ["NewsRepository"]

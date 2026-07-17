"""回填 news_metadata.sentiment / sentiment_score（詞典分類器）。

背景：news 一直沒做情緒分類 → 99.7% 為 unknown、情緒分佈圖恆空。本腳本對既有新聞
以 app.domain.sentiment_lexicon.classify_sentiment 重新分類並批次更新。可重複執行。

用法（從 backend/）：
    cd backend && PYTHONPATH=. uv run python scripts/backfill_news_sentiment.py [only_unknown|all]
預設 only_unknown（只補未分類者）；all 會全部重算。
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.domain.sentiment_lexicon import classify_sentiment


async def main(mode: str) -> None:
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            # where 為硬編字面值（非使用者輸入）→ 無注入風險
            where = "WHERE sentiment = 'unknown' OR sentiment IS NULL" if mode != "all" else ""
            rows = (
                await session.execute(
                    text(f"SELECT id, title, summary FROM news_metadata {where}")  # noqa: S608
                )
            ).all()
            print(f"[info] 待分類 {len(rows)} 則（mode={mode}）")

            updates: list[dict[str, Any]] = []
            for nid, title, summary in rows:
                label, score = classify_sentiment(title, summary)
                updates.append({"nid": nid, "s": label, "sc": score})

            upd = text(
                "UPDATE news_metadata SET sentiment = :s, sentiment_score = :sc WHERE id = :nid"
            ).bindparams(bindparam("nid"))
            written = 0
            for i in range(0, len(updates), 1000):
                chunk = updates[i : i + 1000]
                await session.execute(upd, chunk)
                written += len(chunk)
            await session.commit()

            # 統計
            dist = (
                await session.execute(
                    text("SELECT sentiment, count(*) FROM news_metadata GROUP BY 1 ORDER BY 2 DESC")
                )
            ).all()
            print(f"[done] 更新 {written} 則；分佈 = {dict(dist)}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "only_unknown"))

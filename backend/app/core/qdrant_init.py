"""Qdrant collections idempotent 初始化（PLAN 20.3）。

設計：
- 7 個 collections，全用 Cosine distance + size 768（Gemini text-embedding-004）
- 啟動時 `ensure_collections()` 檢查並補建（不存在才建）
- **不能 DROP/CREATE**，避免重啟丟向量

注意：
- distance / size 設錯 → 補建會失敗（手動處理：管理員介入重建）
- 此函式 idempotent，可在 lifespan 安全呼叫
"""

from __future__ import annotations

from typing import TypedDict

from qdrant_client import AsyncQdrantClient  # type: ignore[import-untyped]
from qdrant_client.http.exceptions import UnexpectedResponse  # type: ignore[import-untyped]
from qdrant_client.http.models import Distance, VectorParams  # type: ignore[import-untyped]

from app.core.logging_config import get_logger
from app.core.qdrant_client import get_qdrant_client

logger = get_logger(__name__)


class CollectionSpec(TypedDict):
    """Qdrant collection 規格。"""

    name: str
    size: int
    distance: str  # "Cosine" / "Euclid" / "Dot"


# PLAN 20.3 — 7 個 collections
COLLECTIONS: list[CollectionSpec] = [
    {"name": "tw_news_v1", "size": 768, "distance": "Cosine"},
    {"name": "tw_announcements_v1", "size": 768, "distance": "Cosine"},
    {"name": "tw_earnings_calls_v1", "size": 768, "distance": "Cosine"},
    {"name": "tw_macro_news_v1", "size": 768, "distance": "Cosine"},
    {"name": "tw_industry_reports_v1", "size": 768, "distance": "Cosine"},
    {"name": "us_news_v1", "size": 768, "distance": "Cosine"},
    {"name": "us_filings_v1", "size": 768, "distance": "Cosine"},
]


_DISTANCE_MAP = {
    "Cosine": Distance.COSINE,
    "Euclid": Distance.EUCLID,
    "Dot": Distance.DOT,
}


def _to_distance(name: str) -> Distance:
    """字串轉 Distance enum；不認識的 fallback Cosine 並警告。"""
    if name not in _DISTANCE_MAP:
        logger.warning("qdrant.distance.unknown", distance=name, fallback="Cosine")
        return Distance.COSINE
    return _DISTANCE_MAP[name]


async def ensure_collection(
    client: AsyncQdrantClient,
    spec: CollectionSpec,
) -> bool:
    """確保單一 collection 存在；不存在則建。

    Returns:
        True 表示 already existed；False 表示 created now。
    """
    name = spec["name"]
    try:
        info = await client.get_collection(collection_name=name)
        # 已存在 — 驗證 vector size 一致（避免 silent mismatch）
        existing_size = info.config.params.vectors.size  # type: ignore[union-attr]
        if existing_size != spec["size"]:
            logger.error(
                "qdrant.collection.size_mismatch",
                collection=name,
                expected=spec["size"],
                actual=existing_size,
            )
        return True
    except (UnexpectedResponse, Exception) as e:
        # 404 / not found → 建立
        msg = str(e).lower()
        if (
            "404" not in msg
            and "not found" not in msg
            and "doesn't exist" not in msg
            and not isinstance(e, UnexpectedResponse)
        ):
            # 非 404 錯誤 → 重拋（避免吞掉認證錯等真實問題）
            raise
        # 建立 collection（idempotent — 若已存在 client 會回 409，我們忽略）
        try:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=spec["size"],
                    distance=_to_distance(spec["distance"]),
                ),
            )
            logger.info("qdrant.collection.created", collection=name)
            return False
        except Exception as create_err:
            # 並發場景：另一個 process 已建立 → 視為成功
            if "already exists" in str(create_err).lower():
                logger.info("qdrant.collection.created_by_other", collection=name)
                return True
            raise


async def ensure_collections() -> dict[str, str]:
    """確保 PLAN 20.3 中 7 個 collections 全部存在。

    Returns:
        {collection_name: "existed" | "created"}
    """
    client = get_qdrant_client()
    results: dict[str, str] = {}
    for spec in COLLECTIONS:
        existed = await ensure_collection(client, spec)
        results[spec["name"]] = "existed" if existed else "created"
    logger.info("qdrant.ensure_collections.done", results=results)
    return results


__all__ = ["COLLECTIONS", "CollectionSpec", "ensure_collection", "ensure_collections"]

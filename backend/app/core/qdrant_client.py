"""Qdrant client wrapper — 用 API key + gRPC（效能比 HTTP 好）。

依 PLAN.md 第 ADR-002 章。

P3 階段：只提供 client，不在 startup 建 collection（P4 / P7 才建）。
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient  # type: ignore[import-untyped]

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


_qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """取得 / 註冊全域 AsyncQdrantClient（單例）。"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            api_key=settings.QDRANT_API_KEY.get_secret_value(),
            prefer_grpc=True,  # gRPC 比 HTTP 快（依 ADR-002）
            timeout=30,
        )
    return _qdrant_client


async def test_qdrant_connection() -> None:
    """startup fail-fast probe：列 collections（不依賴特定 collection 存在）。"""
    client = get_qdrant_client()
    # get_collections 不需 collection 存在，純粹測 auth
    result = await client.get_collections()
    logger.info(
        "qdrant.ready",
        collections_count=len(result.collections) if result.collections else 0,
    )


async def dispose_qdrant_client() -> None:
    """shutdown 時關 client（gRPC channel）。"""
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None
    logger.info("qdrant.client.disposed")


__all__ = ["dispose_qdrant_client", "get_qdrant_client", "test_qdrant_connection"]

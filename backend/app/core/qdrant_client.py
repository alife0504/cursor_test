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
    """取得 / 註冊全域 AsyncQdrantClient（單例）。

    v0.3.0 設定：
    - dev 環境 `https=False`（無 TLS）；prod TLS 由 nginx 終結，client 仍走 plain
    - 預設不啟 prefer_grpc，避免 client 假設 TLS handshake
    - 後續 P4+ 大量 vector write 時可改 prefer_grpc=True，但需確認 server TLS 設定一致
    """
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            api_key=settings.QDRANT_API_KEY.get_secret_value(),
            https=False,  # dev 無 TLS（prod 由 nginx 終結，client 仍走 plain）
            prefer_grpc=False,  # dev 預設用 REST，避免 gRPC TLS handshake 問題
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

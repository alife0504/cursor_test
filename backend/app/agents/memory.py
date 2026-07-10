"""AgentMemory — 決策記憶（還原原版 portfolio_manager 的 past_context）。

設計（依使用者選擇「完整 + 記憶系統」）：
- 用 Qdrant collection `agent_decisions_v1`（768-dim Cosine，與全站一致）儲存歷史決策。
- `store()`：把「當下情勢 → 決策」嵌入後 upsert。
- `retrieve()`：以當下情勢檢索最相似的過往決策，組成 past_context 注入 RiskManager。
- **全程優雅降級**：任何失敗（無 Qdrant / 無 API key / 嵌入錯誤）→ store no-op、retrieve 回 ""，
  絕不讓記憶問題拖垮分析 pipeline（PLAN 14：可觀測但不阻塞）。

嵌入：Gemini text-embedding-004（langchain-google-genai，lazy）。
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_COLLECTION = "agent_decisions_v1"
_EMBED_DIM = 768


class AgentMemory:
    """決策記憶（process 級可共用；無狀態，方法各自開 client）。"""

    def __init__(self, *, collection: str = _COLLECTION) -> None:
        self.collection = collection
        self._embedder: Any = None

    # ── 嵌入（lazy + 優雅降級）──────────────────────────
    async def _embed(self, text: str) -> list[float] | None:
        if not text.strip() or not settings.GOOGLE_API_KEY:
            return None
        try:
            if self._embedder is None:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                self._embedder = GoogleGenerativeAIEmbeddings(
                    model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                    google_api_key=settings.GOOGLE_API_KEY.get_secret_value(),
                )
            vec = await self._embedder.aembed_query(text[:8000])
            return list(vec) if vec else None
        except Exception as exc:
            logger.warning("agent_memory.embed_failed", error=str(exc))
            return None

    async def _ensure(self) -> bool:
        try:
            from app.core.qdrant_client import get_qdrant_client
            from app.core.qdrant_init import ensure_collection

            client = get_qdrant_client()
            await ensure_collection(
                client,
                {"name": self.collection, "size": _EMBED_DIM, "distance": "Cosine"},
            )
            return True
        except Exception as exc:
            logger.warning("agent_memory.ensure_failed", error=str(exc))
            return False

    # ── retrieve ───────────────────────────────────────
    async def retrieve(self, *, symbol: str, region: str, situation: str, k: int = 3) -> str:
        """檢索相似過往決策 → past_context 文字。失敗一律回 ""（不阻塞）。"""
        try:
            vec = await self._embed(situation)
            if vec is None:
                return ""
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            from app.core.qdrant_client import get_qdrant_client

            client = get_qdrant_client()
            # 只撈「同標的」過往決策：原本全 collection 向量搜尋會把別檔股票的 BUY/SELL 當
            # 「類似情勢」注入 RiskManager 造成跨標的污染。以 payload symbol 過濾根除之。
            must = [FieldCondition(key="symbol", match=MatchValue(value=symbol))]
            if region:
                must.append(FieldCondition(key="region", match=MatchValue(value=region)))
            hits = await client.search(
                collection_name=self.collection,
                query_vector=vec,
                query_filter=Filter(must=must),
                limit=max(1, k),
                with_payload=True,
            )
            if not hits:
                return ""
            lines: list[str] = []
            for h in hits:
                p = h.payload or {}
                same = "（同標的）" if p.get("symbol") == symbol else ""
                lines.append(
                    f"- [{p.get('created_at', '?')}] {p.get('symbol', '?')}{same} "
                    f"決策={p.get('action', '?')}（信心{p.get('confidence', '?')}）"
                    f"：{(p.get('reasoning') or '')[:200]}"
                )
            return "過往類似情勢的決策（僅供參考，非保證）：\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("agent_memory.retrieve_failed", symbol=symbol, error=str(exc))
            return ""

    # ── store ──────────────────────────────────────────
    async def store(
        self,
        *,
        symbol: str,
        region: str,
        situation: str,
        decision: dict[str, Any],
        analysis_id: str | None = None,
    ) -> None:
        """把當下情勢 + 決策嵌入並 upsert。失敗一律 no-op（不阻塞）。

        payload 額外存 analysis_id / 進場參考價 / 預留 outcome 欄位，讓日後可用「N 交易日後
        實際報酬 + 相對台股大盤 alpha」回填結算、做真正的反思（reflection）。目前僅記錄不結算，
        結算排程列 v1.1 待辦（見審計 #41）。
        """
        try:
            if not await self._ensure():
                return
            vec = await self._embed(situation)
            if vec is None:
                return
            from qdrant_client.models import PointStruct

            from app.core.qdrant_client import get_qdrant_client

            client = get_qdrant_client()
            payload = {
                "symbol": symbol,
                "region": region,
                "action": decision.get("action"),
                "confidence": decision.get("confidence"),
                "reasoning": (decision.get("reasoning_zh") or "")[:1000],
                "situation": situation[:2000],
                "created_at": datetime.now(tz=UTC).isoformat(),
                "ts": time.time(),
                # 反思用：關聯分析與進場參考價；outcome 待日後排程回填
                "analysis_id": analysis_id,
                "entry_ref_price": decision.get("target_price_low"),
                "realized_return": None,
                "resolved_at": None,
            }
            await client.upsert(
                collection_name=self.collection,
                points=[PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload)],
            )
            logger.info("agent_memory.stored", symbol=symbol, action=decision.get("action"))
        except Exception as exc:
            logger.warning("agent_memory.store_failed", symbol=symbol, error=str(exc))


def build_situation_text(symbol: str, analyses: dict[str, Any]) -> str:
    """從各分析師結論組出「當下情勢」摘要字串（給嵌入用）。"""
    parts = [f"標的：{symbol}"]
    for name, content in (analyses or {}).items():
        text = content if isinstance(content, str) else str(content)
        parts.append(f"[{name}] {text[:600]}")
    return "\n".join(parts)


__all__ = ["AgentMemory", "build_situation_text"]

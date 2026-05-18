"""Phase 11 — Prometheus metrics 單元測試。

不依賴外部服務；直接用 prometheus_client 的 REGISTRY 驗證 counter 可累加。
"""

from __future__ import annotations

import pytest
from prometheus_client import REGISTRY, generate_latest

from app.core.metrics import (
    ANALYSIS_TOTAL,
    LLM_COST_TODAY,
    ORDERS_APPROVED_TOTAL,
)

pytestmark = pytest.mark.unit


def test_analysis_total_counter_increments() -> None:
    """ANALYSIS_TOTAL.labels(status).inc() 後可在 generate_latest 看到。"""
    ANALYSIS_TOTAL.labels(status="queued").inc()
    ANALYSIS_TOTAL.labels(status="queued").inc()
    body = generate_latest(REGISTRY).decode("utf-8")
    assert "analysis_total" in body
    # 至少 ≥ 2（其他 test 也可能 inc 過）
    sample = next(
        s
        for fam in REGISTRY.collect()
        if fam.name == "analysis"
        for s in fam.samples
        if s.name == "analysis_total" and s.labels.get("status") == "queued"
    )
    assert sample.value >= 2.0


def test_llm_cost_today_gauge_set() -> None:
    LLM_COST_TODAY.set(0.42)
    body = generate_latest(REGISTRY).decode("utf-8")
    assert "llm_cost_usd_today" in body
    assert "0.42" in body


def test_orders_approved_total_inc() -> None:
    before = next(
        s.value
        for fam in REGISTRY.collect()
        if fam.name == "orders_approved"
        for s in fam.samples
        if s.name == "orders_approved_total"
    )
    ORDERS_APPROVED_TOTAL.inc()
    after = next(
        s.value
        for fam in REGISTRY.collect()
        if fam.name == "orders_approved"
        for s in fam.samples
        if s.name == "orders_approved_total"
    )
    assert after == before + 1

"""Verifier — 數據接地查核裁判。

定位：完整風險架構（risk_rounds>0）下掛在 `RiskManager → verifier → END`，
對最終 FinalSignal 做「三重接地查核」，只會**降低**信心或翻成 HOLD，
**永不調高**——避免 verifier 自己變成新的失真來源。
（風險層關閉時不掛載，ResearchManager 的訊號直接接 END，行為與舊版一致。）

三重查核：
1. 內部自洽（程式）：價位邏輯（low≤high、BUY 停損<目標、SELL 停損>目標）、confidence 範圍。
2. 數據一致（程式）：action 方向 vs 各 analyst 結構化結論的「方向票」總和（看多/看空/法人買賣超…）。
3. 歷史 base-rate（程式，選用）：action 是否與「同型態歷史前向機率」一致。
   ⚠️ base_rates 必須由 caller 用「當日(含)以前」資料算好傳入（禁止用未來資料 → lookahead）。

設計原則：
- 核心 `verify_signal()` 是**純函數**（無副作用、不打網路），完全可單測。
- LLM critic 為**可選**輔助（llm=None 時略過）；核心不依賴 LLM。
- 單調性保證：final_confidence ≤ original_confidence。
- 可稽核：每個調整都有對應 flag（code + severity + 原因）。

接線：`graph_builder._wire_risk_layer` 會在 risk_rounds>0 時把本節點註冊為
`risk_manager → verifier → END`，並以 SYNTHESIS_COMPLETED 事件 publish 最終訊號。
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ── 可調參數（集中管理，方便 A/B 與消融測試）────────────────
HARD_CONFLICT_NET = 4
"""方向票淨值反向且 |net| ≥ 此值 → 視為硬矛盾，強制 HOLD。"""
SOFT_CONFLICT_NET = 2
"""方向票淨值反向且 |net| ≥ 此值 → 軟矛盾，扣信心。"""
PENALTY_CONFLICT = 30
PENALTY_PRICE_INCOHERENT = 20
PENALTY_LOW_COVERAGE = 15
PENALTY_WEAK_BASERATE = 15
LOW_COVERAGE_THRESHOLD = 0.5
HOLD_CONFIDENCE_FLOOR = 40
"""調整後信心低於此值 → 直接翻 HOLD。"""


class VerificationFlag(BaseModel):
    code: str
    severity: Literal["info", "warn", "critical"]
    detail: str


class VerificationResult(BaseModel):
    verdict: Literal["pass", "caution", "override_hold"]
    original_action: str
    final_action: str
    original_confidence: int
    final_confidence: int = Field(ge=0, le=100)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    net_direction: int
    """各 analyst 方向票淨和（正=偏多，負=偏空）。"""
    flags: list[VerificationFlag] = Field(default_factory=list)


# ── helpers ────────────────────────────────────────────────


def _safe_json(raw: Any) -> dict[str, Any] | None:
    """analyst 寫入的是 model_dump_json()（合法 JSON）或降級純文字（⚠️ 資料不足…）。

    回 dict 表示「有結構化結論」；None 表示「降級/無資料」（用於計算證據覆蓋率）。
    """
    if not isinstance(raw, str):
        return None
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


# 情緒面分析師（新聞情緒聚合）的方向票。
# 註：不對 NewsAnalyst 的 sentiment 另計方向票——它與本表都源自同一批新聞（get_news 7d），
# 兩者各投 ±2 會讓「新聞語氣」被重複計數、對 net 產生高達 ±4 的相關性偏誤（技術/基本面各僅 ±1），
# 且與 analyst_outputs「新聞情緒不是交易訊號」自相矛盾。故新聞方向訊號僅由此情緒面一票代表。
_MARKET_SENTIMENT = {"極度樂觀": 2, "樂觀": 1, "中性": 0, "悲觀": -1, "極度悲觀": -2}
_INST_FLOW = {"大量買超": 2, "小量買超": 1, "中性": 0, "小量賣超": -1, "大量賣超": -2}
_VIEW = {"看多": 1, "看空": -1, "中性": 0}


def _direction_votes(analyses: dict[str, Any]) -> tuple[int, int, int]:
    """彙整方向票。回 (net, n_structured, n_total)。

    以「欄位探測」計票（不依賴 analyst 名稱）：
    - market/fundamental → short_term_view / long_term_view
    - sentiment（情緒面）→ market_sentiment（樂觀/悲觀）— 新聞方向訊號僅由此一票代表
    - chip（籌碼面）→ institutional_flow / margin_trading_signal
    - news（新聞面）：不計方向票（新聞情緒不是交易訊號，且避免與情緒面重複計數）
    """
    net = 0
    n_structured = 0
    n_total = len(analyses)
    for raw in analyses.values():
        d = _safe_json(raw)
        if d is None:
            continue
        n_structured += 1
        net += _VIEW.get(d.get("short_term_view"), 0)
        net += _VIEW.get(d.get("long_term_view"), 0)
        # NewsAnalyst 的 sentiment 不計方向票（見 _MARKET_SENTIMENT 註解：避免與情緒面重複計數）
        net += _MARKET_SENTIMENT.get(d.get("market_sentiment"), 0)
        net += _INST_FLOW.get(d.get("institutional_flow"), 0)
        net += _VIEW.get(d.get("margin_trading_signal"), 0)
    return net, n_structured, n_total


def _dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


# ── 核心：純函數 ────────────────────────────────────────────


def verify_signal(
    signal: dict[str, Any] | None,
    analyses: dict[str, Any] | None,
    *,
    base_rates: dict[str, Any] | None = None,
) -> VerificationResult:
    """對 FinalSignal（dict）做三重查核。純函數、無副作用。

    Args:
        signal: ResearchManager 產出的 FinalSignal.model_dump()。
        analyses: state["analyses"]（{analyst_name: model_dump_json 或降級文字}）。
        base_rates: 選用。形如 {"forward_up_prob": 0.32}，須由 caller 用「當日以前」
            資料算好（防 lookahead）。None → 略過此檢查並標記 info。

    Returns:
        VerificationResult（含調整後 action/confidence 與 flags）。
    """
    signal = signal or {}
    analyses = analyses or {}
    flags: list[VerificationFlag] = []

    action = str(signal.get("action") or "HOLD").upper()
    try:
        conf0 = int(signal.get("confidence") or 0)
    except (TypeError, ValueError):
        conf0 = 0
    conf0 = max(0, min(100, conf0))
    penalty = 0

    net, n_struct, n_total = _direction_votes(analyses)
    coverage = (n_struct / n_total) if n_total else 0.0

    # ── 檢查 1：內部價位自洽 ──────────────────────────
    low = _dec(signal.get("target_price_low"))
    high = _dec(signal.get("target_price_high"))
    sl = _dec(signal.get("stop_loss"))
    incoherent = False
    if low is not None and high is not None and low > high:
        incoherent = True
    if action == "BUY" and sl is not None and (low or high) is not None:
        ref = low if low is not None else high
        if ref is not None and sl >= ref:
            incoherent = True
    if action == "SELL" and sl is not None and (low or high) is not None:
        ref = high if high is not None else low
        if ref is not None and sl <= ref:
            incoherent = True
    if incoherent:
        penalty += PENALTY_PRICE_INCOHERENT
        flags.append(
            VerificationFlag(
                code="PRICE_INCOHERENT",
                severity="critical",
                detail="價位邏輯不自洽（區間顛倒或停損方向錯誤）",
            )
        )

    # ── 檢查 2：action vs 數據方向 ───────────────────
    hard_conflict = False
    if action == "BUY" and net <= -SOFT_CONFLICT_NET:
        penalty += PENALTY_CONFLICT
        hard_conflict = net <= -HARD_CONFLICT_NET
        flags.append(
            VerificationFlag(
                code="ACTION_DATA_CONFLICT",
                severity="critical" if hard_conflict else "warn",
                detail=f"建議 BUY 但分析師方向票偏空（net={net}）",
            )
        )
    elif action == "SELL" and net >= SOFT_CONFLICT_NET:
        penalty += PENALTY_CONFLICT
        hard_conflict = net >= HARD_CONFLICT_NET
        flags.append(
            VerificationFlag(
                code="ACTION_DATA_CONFLICT",
                severity="critical" if hard_conflict else "warn",
                detail=f"建議 SELL 但分析師方向票偏多（net={net}）",
            )
        )

    # ── 檢查 3：歷史 base-rate（選用）────────────────
    if base_rates is None:
        flags.append(
            VerificationFlag(
                code="BASERATE_SKIPPED",
                severity="info",
                detail="未提供歷史 base-rate（接地檢查 3 略過）",
            )
        )
    else:
        up = base_rates.get("forward_up_prob")
        if isinstance(up, int | float):
            if action == "BUY" and up < 0.45:
                penalty += PENALTY_WEAK_BASERATE
                flags.append(
                    VerificationFlag(
                        code="BASERATE_WEAK",
                        severity="warn",
                        detail=f"BUY 但同型態歷史前向上漲機率僅 {up:.0%}",
                    )
                )
            elif action == "SELL" and up > 0.55:
                penalty += PENALTY_WEAK_BASERATE
                flags.append(
                    VerificationFlag(
                        code="BASERATE_WEAK",
                        severity="warn",
                        detail=f"SELL 但同型態歷史前向上漲機率達 {up:.0%}",
                    )
                )

    # ── 證據覆蓋率不足 → 扣信心 ─────────────────────
    if n_total > 0 and coverage < LOW_COVERAGE_THRESHOLD:
        penalty += PENALTY_LOW_COVERAGE
        flags.append(
            VerificationFlag(
                code="LOW_EVIDENCE_COVERAGE",
                severity="warn",
                detail=f"僅 {n_struct}/{n_total} 位分析師有結構化結論",
            )
        )

    # ── 結算：信心只降不升 ───────────────────────────
    final_conf = max(0, min(conf0, conf0 - penalty))
    final_action = action
    verdict: Literal["pass", "caution", "override_hold"] = "pass"

    if hard_conflict or incoherent or final_conf < HOLD_CONFIDENCE_FLOOR:
        if action in ("BUY", "SELL"):
            final_action = "HOLD"
            verdict = "override_hold"
            flags.append(
                VerificationFlag(
                    code="OVERRIDE_HOLD",
                    severity="critical",
                    detail="嚴重矛盾/信心過低 → 保守翻為 HOLD（待人工複核）",
                )
            )
        else:
            verdict = "caution"
    elif penalty > 0:
        verdict = "caution"

    return VerificationResult(
        verdict=verdict,
        original_action=action,
        final_action=final_action,
        original_confidence=conf0,
        final_confidence=final_conf,
        evidence_coverage=round(coverage, 3),
        net_direction=net,
        flags=flags,
    )


# ── 圖節點包裝（risk_rounds>0 時由 _wire_risk_layer 註冊為 risk_manager 後的終結查核）──────


class Verifier:
    """graph node 形式的查核裁判（risk_rounds>0 時掛在 risk_manager 之後）。"""

    role: str = "verifier"

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm  # 預留：可選的 LLM critic；None → 純程式化查核

    async def verify(self, state: dict[str, Any]) -> dict[str, Any]:
        signal = state.get("signal") or {}
        analyses = state.get("analyses") or {}
        result = verify_signal(signal, analyses, base_rates=state.get("base_rates"))

        new_signal = dict(signal)
        new_signal["action"] = result.final_action
        new_signal["confidence"] = result.final_confidence
        new_signal["verification"] = result.model_dump(mode="json")

        logger.info(
            "verifier.done",
            verdict=result.verdict,
            action=f"{result.original_action}->{result.final_action}",
            confidence=f"{result.original_confidence}->{result.final_confidence}",
            net=result.net_direction,
            flags=[f.code for f in result.flags],
        )
        # 把查核結果附加進報告（report_md 由前一節點 risk_manager 產生）
        report = (state.get("report_md") or "") + _render_verification_section(result)
        return {"signal": new_signal, "report_md": report}


_VERDICT_ZH = {
    "pass": "✅ 通過（訊號與數據一致）",
    "caution": "⚠️ 注意（已下修信心）",
    "override_hold": "🛑 保守翻轉為 HOLD（待人工複核）",
}


def _render_verification_section(r: VerificationResult) -> str:
    """產出報告末尾的「接地查核」區塊。"""
    lines = ["", "", "## 接地查核（Verifier）", ""]
    lines.append(f"- **判定**：{_VERDICT_ZH.get(r.verdict, r.verdict)}")
    if r.original_action != r.final_action:
        lines.append(f"- **動作調整**：`{r.original_action}` → `{r.final_action}`")
    if r.original_confidence != r.final_confidence:
        lines.append(f"- **信心調整**：{r.original_confidence} → {r.final_confidence}")
    lines.append(
        f"- **證據覆蓋率**：{r.evidence_coverage:.0%}｜分析師方向票淨值：{r.net_direction}"
    )
    flags = [f for f in r.flags if f.severity != "info"]
    if flags:
        lines.append("- **查核旗標**：")
        lines.extend(f"  - [{f.severity}] {f.detail}" for f in flags)
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "VerificationFlag",
    "VerificationResult",
    "Verifier",
    "verify_signal",
]

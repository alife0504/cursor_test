"""把 LangGraph final_state["analyses"] 轉成前端 AnalystResultCard 要的結構化形狀。

背景（v1.0.2 修補）：
- 每個 Analyst 在 `analyze()` 結束時寫 `analyses[name] = result.model_dump_json()`，
  即把結構化的 Pydantic 結果（MarketAnalysisResult 等）序列化成 JSON 字串放進 state。
- 但 v1.0.1 的 `run_analysis._update_completed` 從未把這份資料寫進
  `analysis_reports.analyst_outputs`，導致前端 AnalystResultCard 永遠 fallback
  到「結構化資料尚未取得」。
- 本模組負責把 state 內各 analyst 的 JSON 轉成前端契約：
  `{type, score, signal, key_points, report_md, metrics}`（見 frontend api-types.ts
  `AnalystOutput`）。

形狀對齊（frontend/src/lib/api-types.ts `AnalystOutput`）：
- `score`：信心度（沿用 analyst 的 confidence 0-100，前端 shortenScore 會處理）
- `signal`：BUY / SELL / HOLD（由 analyst 的看多/看空/中性視角映射；新聞面無交易訊號 → None）
- `key_points`：卡片正面條列的關鍵觀察點（前端預設顯示前 3 點，其餘可展開）
- `report_md`：collapsible「完整報告」內容（用 analyst 的 summary 散文）
- `metrics`：原始結構化數值（指標 / 比率 / 法人動向…），供未來延伸用
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# 看多/看空/中性 → 交易訊號
_VIEW_TO_SIGNAL: dict[str, str] = {
    "看多": "BUY",
    "看空": "SELL",
    "中性": "HOLD",
}


def build_analyst_outputs(
    analyses: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """把 `final_state["analyses"]` 轉成 `{analyst_name: AnalystOutput}`。

    Args:
        analyses: `{analyst_name: json_str_or_dict}`。值通常是 analyst
            `result.model_dump_json()` 產生的 JSON 字串；stub analyst 則是純文字。

    Returns:
        `{analyst_name: {type, score, signal, key_points, report_md, metrics}}`，
        可直接 assign 給 `analysis_reports.analyst_outputs`（JSONB）。
    """
    if not analyses:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for name, raw in analyses.items():
        try:
            out[name] = _build_one(name, raw)
        except Exception as exc:  # 單一 analyst 解析失敗不應拖垮整批
            logger.warning("analyst_outputs.build_failed", analyst=name, error=str(exc))
            out[name] = {"type": name, "report_md": _as_text(raw)}
    return out


# ── 內部 ────────────────────────────────────────────────


def _build_one(name: str, raw: Any) -> dict[str, Any]:
    data = _parse(raw)
    # 非結構化（stub 純文字或無法解析）→ 只放 report_md
    if not isinstance(data, dict):
        return {"type": name, "report_md": _as_text(raw)}

    builder = _BUILDERS.get(name, _build_generic)
    output = builder(data)
    output["type"] = name
    # 清掉 None / 空 list，讓前端 hasOutput 判斷乾淨
    return {k: v for k, v in output.items() if v not in (None, [], {}, "")}


def _build_market(d: dict[str, Any]) -> dict[str, Any]:
    points: list[str] = []
    if d.get("trend"):
        points.append(f"技術趨勢：{d['trend']}")
    if d.get("short_term_view"):
        points.append(f"短線觀點：{d['short_term_view']}")
    sup = d.get("support_levels") or []
    res = d.get("resistance_levels") or []
    if sup and res:
        points.append(f"支撐 {sup[0]} / 壓力 {res[-1]}")
    for k, v in (d.get("key_indicators") or {}).items():
        points.append(f"{k}：{v}")
    points += [f"風險：{r}" for r in (d.get("risk_factors") or [])]
    return {
        "score": d.get("confidence"),
        "signal": _VIEW_TO_SIGNAL.get(str(d.get("short_term_view") or "")),
        "key_points": points,
        "report_md": d.get("summary"),
        "metrics": {
            "trend": d.get("trend"),
            "key_indicators": d.get("key_indicators"),
            "support_levels": d.get("support_levels"),
            "resistance_levels": d.get("resistance_levels"),
        },
    }


def _build_fundamental(d: dict[str, Any]) -> dict[str, Any]:
    points: list[str] = []
    if d.get("valuation"):
        points.append(f"評價：{d['valuation']}")
    if d.get("financial_strength"):
        points.append(f"財務強度：{d['financial_strength']}")
    if d.get("long_term_view"):
        points.append(f"長線觀點：{d['long_term_view']}")
    if d.get("growth_outlook"):
        points.append(f"成長展望：{d['growth_outlook']}")
    for k, v in (d.get("key_ratios") or {}).items():
        points.append(f"{k}：{v}")
    points += [f"風險：{r}" for r in (d.get("risk_factors") or [])]
    return {
        "score": d.get("confidence"),
        "signal": _VIEW_TO_SIGNAL.get(str(d.get("long_term_view") or "")),
        "key_points": points,
        "report_md": d.get("summary"),
        "metrics": {
            "valuation": d.get("valuation"),
            "financial_strength": d.get("financial_strength"),
            "key_ratios": d.get("key_ratios"),
        },
    }


def _build_news(d: dict[str, Any]) -> dict[str, Any]:
    points: list[str] = []
    if d.get("sentiment"):
        points.append(f"新聞情緒：{d['sentiment']}")
    if d.get("macro_bias") and d.get("macro_bias") != "未提供":
        points.append(f"總經偏向：{d['macro_bias']}")
    if d.get("impact_assessment"):
        points.append(f"影響評估：{d['impact_assessment']}")
    if d.get("macro_context"):
        points.append(f"總經脈絡：{d['macro_context']}")
    points += [f"焦點：{t}" for t in (d.get("key_topics") or [])]
    return {
        "score": d.get("confidence"),
        # 新聞情緒不是交易訊號 → 不映射 BUY/SELL
        "signal": None,
        "key_points": points,
        "report_md": d.get("summary"),
        "metrics": {
            "sentiment": d.get("sentiment"),
            "macro_bias": d.get("macro_bias"),
            "macro_context": d.get("macro_context"),
            "key_topics": d.get("key_topics"),
            "supporting_articles": d.get("supporting_articles"),
        },
    }


# 市場情緒 → 交易訊號（情緒面：樂觀偏多、悲觀偏空；中性 HOLD）
_SENTIMENT_TO_SIGNAL: dict[str, str] = {
    "極度樂觀": "BUY",
    "樂觀": "BUY",
    "中性": "HOLD",
    "悲觀": "SELL",
    "極度悲觀": "SELL",
}


def _build_sentiment(d: dict[str, Any]) -> dict[str, Any]:
    """情緒面（新聞情緒聚合）。"""
    points: list[str] = []
    if d.get("market_sentiment"):
        points.append(f"市場情緒：{d['market_sentiment']}")
    if d.get("sentiment_score") is not None:
        points.append(f"情緒分數：{d['sentiment_score']}")
    if d.get("buzz_level"):
        points.append(f"討論熱度：{d['buzz_level']}")
    if d.get("momentum"):
        points.append(f"情緒動能：{d['momentum']}")
    if d.get("contrarian_flag"):
        points.append("⚠️ 極端情緒，留意反轉風險")
    points += [f"題材：{t}" for t in (d.get("key_drivers") or [])]
    points += [f"風險：{r}" for r in (d.get("risk_factors") or [])]
    return {
        "score": d.get("confidence"),
        # 情緒是輿論氛圍，僅供參考方向，不當強交易訊號
        "signal": _SENTIMENT_TO_SIGNAL.get(str(d.get("market_sentiment") or "")),
        "key_points": points,
        "report_md": d.get("summary"),
        "metrics": {
            "market_sentiment": d.get("market_sentiment"),
            "sentiment_score": d.get("sentiment_score"),
            "buzz_level": d.get("buzz_level"),
            "momentum": d.get("momentum"),
            "contrarian_flag": d.get("contrarian_flag"),
        },
    }


def _build_chip(d: dict[str, Any]) -> dict[str, Any]:
    """籌碼面（三大法人/融資券/月營收）。"""
    points: list[str] = []
    if d.get("institutional_flow"):
        points.append(f"法人動向：{d['institutional_flow']}")
    if d.get("margin_trading_signal"):
        points.append(f"融資融券訊號：{d['margin_trading_signal']}")
    if d.get("retail_sentiment"):
        points.append(f"散戶情緒：{d['retail_sentiment']}")
    if d.get("foreign_position_change"):
        points.append(f"外資部位：{d['foreign_position_change']}")
    points += [f"風險：{r}" for r in (d.get("risk_factors") or [])]
    return {
        "score": d.get("confidence"),
        "signal": _VIEW_TO_SIGNAL.get(str(d.get("margin_trading_signal") or "")),
        "key_points": points,
        "report_md": d.get("summary"),
        "metrics": {
            "institutional_flow": d.get("institutional_flow"),
            "margin_trading_signal": d.get("margin_trading_signal"),
            "retail_sentiment": d.get("retail_sentiment"),
        },
    }


def _build_generic(d: dict[str, Any]) -> dict[str, Any]:
    """未知 analyst：盡量抓共通欄位。"""
    return {
        "score": d.get("confidence"),
        "key_points": list(d.get("key_points") or d.get("risk_factors") or []),
        "report_md": d.get("summary") or d.get("report_md"),
        "metrics": {k: v for k, v in d.items() if k not in ("summary", "confidence")},
    }


_BUILDERS = {
    "market": _build_market,
    "fundamental": _build_fundamental,
    "news": _build_news,
    "sentiment": _build_sentiment,
    "chip": _build_chip,
}


def _parse(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


def _as_text(raw: Any) -> str:
    return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)


__all__ = ["build_analyst_outputs"]

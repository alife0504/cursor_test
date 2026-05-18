"""把 LLM final signal 轉成 PendingOrder（P14）。

依 PLAN.md 第 10 章跨市場 + 第 14 章穩定性 + ADR-007 手動核准下單流程。

設計：
- HOLD → 不建單（回 None）。
- BUY / SELL → 建 PendingOrder(status="PENDING") 等 admin 核准。
- qty 計算：v1.0 暫用「固定預算 / target_price」（PLAN 14 已知陷阱 — 沒有真實
  portfolio balance，避免拖累 P14 完成）。`position_size_pct` 純記在 audit。
- entry_price / stop_loss / take_profit 從 signal 取（FinalSignal schema 已定義）。

進 DB 由 caller 控制（注 session.add(order) 後 commit）。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from app.core.logging_config import get_logger
from app.models.order import PendingOrder

logger = get_logger(__name__)


# v1.0 預設「每張訂單投入」固定金額（USD-equivalent；台股以 TWD 計）。
# 真實 portfolio balance 需 P16 用戶持倉管理上線後再串接（PLAN 已知陷阱）。
DEFAULT_NOTIONAL_USD: Decimal = Decimal("10000")


def _decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def calculate_qty(target_price: Decimal | None, *, market: str | None = None) -> int:
    """估算下單股數。

    Args:
        target_price: 進場參考價（FinalSignal.target_price_low）。
        market: 市場代碼；台股最小單位通常為 1000 股（v1.0 暫忽略，整數股即可）。

    Returns:
        正整數股數；target_price ≤ 0 或缺資料 → 回 1（保留訂單骨架，由 admin 補單價）。
    """
    if target_price is None or target_price <= 0:
        return 1
    qty = int((DEFAULT_NOTIONAL_USD / target_price).to_integral_value())
    return max(qty, 1)


def signal_to_pending_order(
    signal: dict[str, Any] | None,
    *,
    analysis_id: str | UUID,
    user_id: str | UUID,
    symbol: str,
    market: str,
) -> PendingOrder | None:
    """把 final signal 轉成 PendingOrder 物件（尚未 add 進 session）。

    Args:
        signal: FinalSignal.model_dump() 結果 dict。
        analysis_id: 來源分析報告 ID。
        user_id: 下單用戶 ID。
        symbol: 股票代號。
        market: 市場代碼（TWSE / TPEX / NASDAQ / NYSE / AMEX）。

    Returns:
        `PendingOrder` 實例（status=PENDING, version=1）；HOLD 訊號 → None。

    Raises:
        ValueError: signal["action"] 不在 ("BUY", "SELL", "HOLD") 範圍。
    """
    if not signal:
        logger.info("orders_decision.no_signal", analysis_id=str(analysis_id), symbol=symbol)
        return None

    action = signal.get("action")
    if action not in ("BUY", "SELL", "HOLD"):
        raise ValueError(f"signal.action 必須是 BUY/SELL/HOLD，收到：{action!r}")

    if action == "HOLD":
        logger.info(
            "orders_decision.hold_no_order",
            analysis_id=str(analysis_id),
            symbol=symbol,
        )
        return None

    target_price = _decimal_or_none(signal.get("target_price_low"))
    target_high = _decimal_or_none(signal.get("target_price_high"))
    stop_loss = _decimal_or_none(signal.get("stop_loss"))

    qty = calculate_qty(target_price, market=market)

    order = PendingOrder(
        id=uuid4(),
        user_id=_uuid(user_id),
        analysis_id=_uuid(analysis_id),
        symbol=symbol,
        market=market,
        side=action,
        qty=qty,
        target_price=target_price,
        stop_loss=stop_loss,
        take_profit=target_high,
        status="PENDING",
        version=1,
    )
    logger.info(
        "orders_decision.created",
        analysis_id=str(analysis_id),
        symbol=symbol,
        market=market,
        side=action,
        qty=qty,
        target_price=str(target_price) if target_price else None,
        stop_loss=str(stop_loss) if stop_loss else None,
        take_profit=str(target_high) if target_high else None,
    )
    return order


def _uuid(v: str | UUID) -> UUID:
    """容錯：str → UUID。"""
    if isinstance(v, UUID):
        return v
    return UUID(str(v))


__all__ = [
    "DEFAULT_NOTIONAL_USD",
    "calculate_qty",
    "signal_to_pending_order",
]

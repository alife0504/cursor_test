"""把 LLM final signal 轉成 PendingOrder（P14）。

依 PLAN.md 第 10 章跨市場 + 第 14 章穩定性 + ADR-007 手動核准下單流程。

設計：
- HOLD → 不建單（回 None）。
- BUY / SELL → 建 PendingOrder(status="PENDING") 等 admin 核准。
- qty 計算：v1.0 用「名目預算 / target_price」（PLAN 14 已知陷阱 — 沒有真實
  portfolio balance，避免拖累 P14 完成）。名目預算再依 `position_size_pct`（風險經理
  加減碼強弱 0~100）縮放，讓部位建議真正影響下單股數（缺值＝滿倉、向後相容）。
- entry_price / stop_loss / take_profit 從 signal 取（FinalSignal schema 已定義）。

進 DB 由 caller 控制（注 session.add(order) 後 commit）。
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from app.core.logging_config import get_logger
from app.models.order import PendingOrder

logger = get_logger(__name__)


# v1.0 預設「每張訂單投入」固定金額（依市場計價幣別分開）。
# 真實 portfolio balance 需 P16 用戶持倉管理上線後再串接（PLAN 已知陷阱）。
DEFAULT_NOTIONAL_USD: Decimal = Decimal("10000")
"""美股每張訂單預設投入（USD）。"""
DEFAULT_NOTIONAL_TWD: Decimal = Decimal("100000")
"""台股每張訂單預設投入（TWD，約 NT$10 萬；足以買 1~2 張中價位個股）。"""
TW_LOT_SIZE: int = 1000
"""台股一張（整股交易單位）= 1000 股。"""

_TW_MARKETS = frozenset({"TWSE", "TPEX", "TW"})


def _is_tw_market(market: str | None) -> bool:
    return (market or "").upper() in _TW_MARKETS


def _decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _position_scale(position_size_pct: Any) -> Decimal:
    """把 FinalSignal.position_size_pct（0~100 的加減碼強弱）轉成名目金額縮放係數。

    - 缺值(None)/不合法 → 1.0（＝滿倉預設，向後相容）。
    - 明確的 0% → 0.0（不加碼；qty 交由下游最小交易單位決定骨架單）——不可與「缺值」混為
      一談把低信心 0% 反而放成滿倉。
    - 其餘夾在 (0, 1]。
    ⚠️ 注意：台股 min_unit=1000 股、floor 後至少一張，故縮放後名目若小於「一張成本」仍會被
    墊回一張——sub-lot 減碼在台股中價股上受此限制（v1.0 無真實 portfolio 的已知取捨）。
    """
    if position_size_pct is None:
        return Decimal("1")
    try:
        pct = Decimal(str(position_size_pct))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("1")
    if pct <= 0:
        return Decimal("0")
    if pct > 100:
        pct = Decimal("100")
    return pct / Decimal("100")


def calculate_qty(
    target_price: Decimal | None,
    *,
    market: str | None = None,
    position_size_pct: Any = None,
) -> int:
    """估算下單股數。

    台股（TWSE/TPEX）以「整張」為交易單位（1 張 = 1000 股），故無條件捨去到整張、
    至少 1 張；美股以「股」為單位、至少 1 股。預算依市場計價幣別分開。

    Args:
        target_price: 進場參考價（FinalSignal.target_price_low）。
        market: 市場代碼；決定計價幣別預算與最小交易單位。
        position_size_pct: 風險經理的加碼/減碼強弱（0~100）。用來縮放名目金額——高信心
            重倉（如 80）投入較多、輕倉（如 20）投入較少；缺值＝滿倉（向後相容）。

    Returns:
        正整數股數；target_price ≤ 0 或缺資料 → 回最小交易單位（台股 1000、美股 1），
        保留訂單骨架由 admin 補單價。
    """
    is_tw = _is_tw_market(market)
    min_unit = TW_LOT_SIZE if is_tw else 1
    if target_price is None or target_price <= 0:
        return min_unit
    base_notional = DEFAULT_NOTIONAL_TWD if is_tw else DEFAULT_NOTIONAL_USD
    notional = base_notional * _position_scale(position_size_pct)
    # 明示無條件捨去（ROUND_DOWN）：Decimal 預設 context 為 ROUND_HALF_EVEN，可買股數小數 ≥.5 時
    # 會進位，跨越整張邊界會多買一整張、下單金額超出預算（違反本函式「無條件捨去到整張」契約）。
    raw = int((notional / target_price).to_integral_value(rounding=ROUND_DOWN))
    if is_tw:
        lots = raw // TW_LOT_SIZE  # 無條件捨去到整張
        return max(lots, 1) * TW_LOT_SIZE
    return max(raw, 1)


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

    # position_size_pct（風險經理加減碼強弱）縮放名目金額 → 真正影響下單股數
    qty = calculate_qty(
        target_price, market=market, position_size_pct=signal.get("position_size_pct")
    )

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
    "DEFAULT_NOTIONAL_TWD",
    "DEFAULT_NOTIONAL_USD",
    "TW_LOT_SIZE",
    "calculate_qty",
    "signal_to_pending_order",
]

import { describe, expect, test } from "vitest";

import { computePositions } from "@/hooks/usePortfolio";
import type { OrderSummary } from "@/lib/api-types";

function mkOrder(o: Partial<OrderSummary>): OrderSummary {
  return {
    id: o.id ?? "00000000-0000-0000-0000-000000000000",
    user_id: "u",
    analysis_id: null,
    symbol: o.symbol ?? "2330",
    market: o.market ?? "TWSE",
    side: o.side ?? "BUY",
    qty: o.qty ?? 0,
    target_price: o.target_price ?? "100",
    stop_loss: null,
    take_profit: null,
    status: o.status ?? "APPROVED",
    reviewed_by: null,
    reviewed_at: null,
    review_notes: null,
    version: 1,
    created_at: "2025-01-01T00:00:00Z",
    expires_at: null,
  };
}

describe("computePositions", () => {
  test("只計算 APPROVED 訂單", () => {
    const orders: OrderSummary[] = [
      mkOrder({ symbol: "2330", side: "BUY", qty: 100, status: "PENDING" }),
      mkOrder({ symbol: "2330", side: "BUY", qty: 50, status: "APPROVED" }),
    ];
    const pos = computePositions(orders);
    expect(pos.length).toBe(1);
    expect(pos[0].qty).toBe(50);
  });

  test("BUY 後 SELL 部分平倉:qty = buy - sell", () => {
    const orders = [
      mkOrder({ symbol: "2330", side: "BUY", qty: 100, target_price: "100" }),
      mkOrder({ symbol: "2330", side: "SELL", qty: 30, target_price: "120" }),
    ];
    const pos = computePositions(orders);
    expect(pos.length).toBe(1);
    expect(pos[0].qty).toBe(70);
  });

  test("BUY 然後完全 SELL:qty=0 → 從 positions 排除", () => {
    const orders = [
      mkOrder({ symbol: "2330", side: "BUY", qty: 100 }),
      mkOrder({ symbol: "2330", side: "SELL", qty: 100 }),
    ];
    const pos = computePositions(orders);
    expect(pos.length).toBe(0);
  });

  test("不同 symbol 各自累計", () => {
    const orders = [
      mkOrder({ symbol: "2330", side: "BUY", qty: 100 }),
      mkOrder({ symbol: "AAPL", market: "NASDAQ", side: "BUY", qty: 10 }),
    ];
    const pos = computePositions(orders);
    expect(pos.length).toBe(2);
    expect(pos.find((p) => p.symbol === "2330")?.qty).toBe(100);
    expect(pos.find((p) => p.symbol === "AAPL")?.qty).toBe(10);
  });

  test("空 orders → 空 positions", () => {
    expect(computePositions([])).toEqual([]);
  });
});

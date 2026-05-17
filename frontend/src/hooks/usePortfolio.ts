"use client";

import { useMemo } from "react";

import { useOrders } from "@/hooks/useOrders";
import type { OrderSummary } from "@/lib/api-types";

// Phase 17 § J / § K:Portfolio
//   - 後端 P17 未補 portfolio/positions / portfolio/history 專屬 endpoint(v7.0 不擴大後端)
//   - 客戶端聚合:從 orders 篩 APPROVED 算 positions、用全部 orders 當 trade history
//   - v1.1 若後端加 endpoint,把這個 hook 換掉即可

export interface PortfolioPosition {
  symbol: string;
  market: string;
  qty: number;
  avg_cost: string;
  total_cost: string;
}

// 從 orders 計算每個 symbol 的 net position
export function computePositions(orders: OrderSummary[]): PortfolioPosition[] {
  const map = new Map<string, PortfolioPosition>();
  for (const o of orders) {
    if (o.status !== "APPROVED") continue;
    const key = `${o.symbol}|${o.market}`;
    const sign = o.side === "BUY" ? 1 : -1;
    const qty = sign * o.qty;
    const price = Number(o.target_price ?? 0);
    const existing = map.get(key);
    if (!existing) {
      map.set(key, {
        symbol: o.symbol,
        market: o.market,
        qty,
        avg_cost: price.toString(),
        total_cost: (price * qty).toString(),
      });
    } else {
      const newQty = existing.qty + qty;
      // BUY 累計成本;SELL 不增加 total_cost
      const newTotalCost =
        sign > 0
          ? Number(existing.total_cost) + price * qty
          : Number(existing.total_cost);
      const newAvg = newQty !== 0 ? newTotalCost / newQty : 0;
      map.set(key, {
        symbol: o.symbol,
        market: o.market,
        qty: newQty,
        avg_cost: newAvg.toString(),
        total_cost: newTotalCost.toString(),
      });
    }
  }
  // 過濾 qty=0(已平倉)
  return Array.from(map.values()).filter((p) => p.qty !== 0);
}

// hook:positions = 聚合 APPROVED orders
export function usePositions() {
  const orders = useOrders({ status: "APPROVED", limit: 100 });
  const items = orders.data?.items;
  const positions = useMemo(() => {
    if (!items) return [];
    return computePositions(items);
  }, [items]);
  return {
    ...orders,
    positions,
  };
}

// hook:trade history = 全部 orders
export interface UseTradeHistoryParams {
  symbol?: string | null;
  side?: "BUY" | "SELL" | null;
  cursor?: string | null;
  limit?: number;
}

export function useTradeHistory(params: UseTradeHistoryParams = {}) {
  const { symbol, side, cursor, limit = 50 } = params;
  const q = useOrders({ cursor, limit });
  const filtered = useMemo(() => {
    if (!q.data?.items) return [];
    return q.data.items.filter((o) => {
      if (symbol && o.symbol !== symbol) return false;
      if (side && o.side !== side) return false;
      return true;
    });
  }, [q.data?.items, symbol, side]);
  return { ...q, items: filtered };
}

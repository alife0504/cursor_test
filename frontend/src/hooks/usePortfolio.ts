"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { useOrders } from "@/hooks/useOrders";
import { api, type ApiEnvelope } from "@/lib/api";
import type { OrderSummary } from "@/lib/api-types";

// Phase 17 § J / § K:Portfolio
//   - positions 改讀後端權威 GET /portfolio/positions（核准時已淨額合併的 portfolio_positions）。
//     原「最新 100 筆 APPROVED 訂單客戶端重算」對 >100 單帳號會截斷最舊開倉單→幻影空單、均價失真。
//   - trade history 仍用 orders（歷史流水，非淨額）。

export interface PortfolioPosition {
  symbol: string;
  market: string;
  qty: number;
  avg_cost: string;
  total_cost: string;
  realized_pnl?: string;
}

// hook:positions = 讀後端權威 portfolio_positions（per-user、核准時已淨額合併）
export function usePositions() {
  const query = useQuery({
    queryKey: ["portfolio", "positions"],
    staleTime: 30_000,
    queryFn: async () => {
      const res =
        await api.get<ApiEnvelope<PortfolioPosition[]>>("/portfolio/positions");
      return res.data.data ?? [];
    },
  });
  return {
    ...query,
    positions: query.data ?? [],
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

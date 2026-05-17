"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { OHLCVPoint, StockDetail, StockSummary } from "@/lib/api-types";

// Phase 16 § L:股票相關 React Query hooks
//   - useStocks(q, market):股票列表(支援搜尋 / 市場過濾)
//   - useStockDetail(symbol):股票詳情
//   - useOhlcv(symbol, start, end):OHLCV 資料

export interface UseStocksParams {
  q?: string;
  market?: string;
  cursor?: string | null;
  limit?: number;
}

export function useStocks(params: UseStocksParams = {}, enabled = true) {
  const { q, market, cursor, limit = 50 } = params;
  return useQuery({
    queryKey: ["stocks", { q, market, cursor, limit }],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<StockSummary[]>>("/stocks", {
        params: {
          q: q || undefined,
          market: market || undefined,
          cursor: cursor || undefined,
          limit,
        },
      });
      return {
        items: res.data.data ?? [],
        nextCursor: res.data.pagination?.next_cursor ?? null,
        hasMore: res.data.pagination?.has_more ?? false,
      };
    },
  });
}

export function useStockDetail(symbol: string | null | undefined) {
  return useQuery({
    queryKey: ["stocks", symbol],
    enabled: !!symbol,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<StockDetail>>(
        `/stocks/${encodeURIComponent(symbol as string)}`,
      );
      return res.data.data;
    },
  });
}

export interface UseOhlcvParams {
  symbol: string | null | undefined;
  start: string;
  end: string;
  interval?: string;
}

export function useOhlcv({ symbol, start, end, interval = "daily" }: UseOhlcvParams) {
  return useQuery({
    queryKey: ["stocks", symbol, "ohlcv", start, end, interval],
    enabled: !!symbol && !!start && !!end,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<OHLCVPoint[]>>(
        `/stocks/${encodeURIComponent(symbol as string)}/ohlcv`,
        { params: { start, end, interval } },
      );
      return res.data.data ?? [];
    },
  });
}

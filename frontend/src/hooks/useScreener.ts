"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { ScreenerFilters, ScreenerRow } from "@/lib/api-types";

// Phase 17 § E:選股篩選器 hook
//   - 把 form filters 轉成 query params(後端用大寫 alias:PE_min/PE_max/RSI_min/RSI_max)
//   - cursor pagination(後端 envelope.pagination)
//   - dividend_yield_min / eps_growth_min / market_cap_min:後端用 snake_case

export interface UseScreenerParams extends ScreenerFilters {
  cursor?: string | null;
  limit?: number;
  enabled?: boolean;
}

export function useScreener(params: UseScreenerParams = {}) {
  const {
    market = "TW",
    PE_min,
    PE_max,
    dividend_yield_min,
    eps_growth_min,
    RSI_min,
    RSI_max,
    market_cap_min,
    industry,
    sort = "symbol",
    order = "asc",
    cursor,
    limit = 50,
    enabled = true,
  } = params;
  return useQuery({
    queryKey: [
      "screener",
      {
        market,
        PE_min,
        PE_max,
        dividend_yield_min,
        eps_growth_min,
        RSI_min,
        RSI_max,
        market_cap_min,
        industry,
        sort,
        order,
        cursor,
        limit,
      },
    ],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<ScreenerRow[]>>("/screener", {
        params: {
          market,
          PE_min: PE_min ?? undefined,
          PE_max: PE_max ?? undefined,
          dividend_yield_min: dividend_yield_min ?? undefined,
          eps_growth_min: eps_growth_min ?? undefined,
          RSI_min: RSI_min ?? undefined,
          RSI_max: RSI_max ?? undefined,
          market_cap_min: market_cap_min ?? undefined,
          industry: industry || undefined,
          sort,
          order,
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

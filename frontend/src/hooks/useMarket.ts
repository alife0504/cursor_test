"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { MarketOverview, MoverRow } from "@/lib/api-types";

// Phase 16 § B / § L:大盤 / 漲跌排行 hooks(dashboard 用)
//   - useMarketOverview(market)
//   - useMarketMovers(type, market, limit)

export function useMarketOverview(market = "TW", enabled = true) {
  return useQuery({
    queryKey: ["market", "overview", market],
    enabled,
    staleTime: 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<MarketOverview>>(
        "/market/overview",
        { params: { market } },
      );
      return res.data.data;
    },
  });
}

export function useMarketMovers(
  type: "gainers" | "losers" | "volume" = "gainers",
  market = "TW",
  limit = 10,
  enabled = true,
) {
  return useQuery({
    queryKey: ["market", "movers", { type, market, limit }],
    enabled,
    staleTime: 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<MoverRow[]>>("/market/movers", {
        params: { type, market, limit },
      });
      return res.data.data ?? [];
    },
  });
}

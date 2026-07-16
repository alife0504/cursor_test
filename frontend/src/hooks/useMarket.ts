"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  CalendarEvent,
  MarketOverview,
  MoverRow,
  RealtimeSnapshot,
} from "@/lib/api-types";

// Phase 16 § B / § L:大盤 / 漲跌排行 hooks(dashboard 用)
//   - useMarketOverview(market)
//   - useMarketMovers(type, market, limit)
//   - useRealtimeIndex() / useRealtimeStock(symbols) — 盤中即時報價（輪詢）

const TW_TIMEZONE = "Asia/Taipei";
/** 盤中輪詢間隔。後端有 5 秒全市場快照快取，故上游用量與開幾個頁面無關。 */
export const REALTIME_POLL_MS = 5_000;

/** 台北時間是否為台股盤中（週一~五 09:00–13:30）。收盤後就不該再輪詢。 */
export function isTwMarketOpen(now: Date = new Date()): boolean {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TW_TIMEZONE,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const get = (t: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === t)?.value ?? "";

  const weekday = get("weekday");
  if (weekday === "Sat" || weekday === "Sun") return false;

  const minutes = Number(get("hour")) * 60 + Number(get("minute"));
  return minutes >= 9 * 60 && minutes <= 13 * 60 + 30;
}

/** 即時大盤指數（加權 / 櫃買）。盤中每 5 秒更新，收盤後只抓一次不再輪詢。 */
export function useRealtimeIndex(enabled = true) {
  return useQuery({
    queryKey: ["market", "realtime", "index"],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => (isTwMarketOpen() ? REALTIME_POLL_MS : false),
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RealtimeSnapshot>>(
        "/market/realtime/index",
      );
      return res.data.data;
    },
  });
}

/** 即時個股報價。symbols 為代號陣列；空陣列時不發請求。 */
export function useRealtimeStock(symbols: string[], enabled = true) {
  const key = symbols.join(",");
  return useQuery({
    queryKey: ["market", "realtime", "stock", key],
    enabled: enabled && symbols.length > 0,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => (isTwMarketOpen() ? REALTIME_POLL_MS : false),
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RealtimeSnapshot>>(
        "/market/realtime/stock",
        { params: { symbols: key } },
      );
      return res.data.data;
    },
  });
}

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

/** 財報日曆（法定申報期限 + 除權息）。事件變動慢，快取久一點。 */
export function useMarketCalendar(from: string, to: string, market = "TW") {
  return useQuery({
    queryKey: ["market", "calendar", { from, to, market }],
    staleTime: 10 * 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<CalendarEvent[]>>("/market/calendar", {
        params: { from, to, market },
      });
      return res.data.data;
    },
  });
}

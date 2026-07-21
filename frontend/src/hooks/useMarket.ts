"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  CalendarEvent,
  MarketOverview,
  MoverRow,
  RealtimeOverview,
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
    refetchIntervalInBackground: true,
    // 開啟頁面／切回分頁一律重抓最新：全域 refetchOnWindowFocus=false（避免非即時查詢
    // 請求風暴），但即時報價必須覆寫——瀏覽器會把隱藏分頁的計時器節流到約每分鐘一次，
    // 不重抓的話切回來會先看到最多一分鐘前的舊價。
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
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
    refetchIntervalInBackground: true,
    // 開啟頁面／切回分頁一律重抓最新：全域 refetchOnWindowFocus=false（避免非即時查詢
    // 請求風暴），但即時報價必須覆寫——瀏覽器會把隱藏分頁的計時器節流到約每分鐘一次，
    // 不重抓的話切回來會先看到最多一分鐘前的舊價。
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RealtimeSnapshot>>(
        "/market/realtime/stock",
        { params: { symbols: key } },
      );
      return res.data.data;
    },
  });
}

/** 台指期是否開盤（台北時間）。含日盤與夜盤：
 *  - 日盤 08:45–13:45（週一~五）
 *  - 夜盤 15:00–翌日 05:00；前半(當日 15:00 後)週一~五、後半(翌日 05:00 前)週二~六。
 */
export function isTwFuturesOpen(now: Date = new Date()): boolean {
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
  const min = Number(get("hour")) * 60 + Number(get("minute"));

  const isWeekday = weekday !== "Sat" && weekday !== "Sun"; // 週一~五
  const isTueToSat = weekday !== "Sun" && weekday !== "Mon"; // 週二~六（承接前一日夜盤尾）

  const daySession = min >= 8 * 60 + 45 && min <= 13 * 60 + 45; // 08:45–13:45
  const nightEve = min >= 15 * 60; // 15:00–24:00（當日）
  const nightMorn = min <= 5 * 60; // 00:00–05:00（翌日）

  if (daySession || nightEve) return isWeekday;
  if (nightMorn) return isTueToSat;
  return false;
}

/** 即時期貨報價。contract=台指期 TXF。
 *  allDay=false → 只在日盤/夜盤時段輪詢；allDay=true → 全日每 5 秒輪詢（台指全）。 */
export function useRealtimeFutures(
  ids: string[] = ["TXF"],
  enabled = true,
  allDay = false,
) {
  const key = ids.join(",");
  return useQuery({
    queryKey: ["market", "realtime", "futures", key],
    enabled: enabled && ids.length > 0,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () =>
      allDay || isTwFuturesOpen() ? REALTIME_POLL_MS : false,
    refetchIntervalInBackground: true,
    // 開啟頁面／切回分頁一律重抓最新：全域 refetchOnWindowFocus=false（避免非即時查詢
    // 請求風暴），但即時報價必須覆寫——瀏覽器會把隱藏分頁的計時器節流到約每分鐘一次，
    // 不重抓的話切回來會先看到最多一分鐘前的舊價。
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RealtimeSnapshot>>(
        "/market/realtime/futures",
        { params: { ids: key } },
      );
      return res.data.data;
    },
  });
}

/** 即時大盤（漲跌家數/總量）。僅 TW；盤中每 5 秒，收盤停輪詢。data 為 null 表即時不可用。 */
export function useRealtimeOverview(enabled = true) {
  return useQuery({
    queryKey: ["market", "realtime", "overview"],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => (isTwMarketOpen() ? REALTIME_POLL_MS : false),
    refetchIntervalInBackground: true,
    // 開啟頁面／切回分頁一律重抓最新：全域 refetchOnWindowFocus=false（避免非即時查詢
    // 請求風暴），但即時報價必須覆寫——瀏覽器會把隱藏分頁的計時器節流到約每分鐘一次，
    // 不重抓的話切回來會先看到最多一分鐘前的舊價。
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RealtimeOverview | null>>(
        "/market/realtime/overview",
      );
      return res.data.data ?? null;
    },
  });
}

/** 即時漲跌 / 成交量榜。僅 TW；盤中每 5 秒。data 為 null 表即時不可用。 */
export function useRealtimeMovers(
  type: "gainers" | "losers" | "volume" = "gainers",
  limit = 10,
  enabled = true,
) {
  return useQuery({
    queryKey: ["market", "realtime", "movers", { type, limit }],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => (isTwMarketOpen() ? REALTIME_POLL_MS : false),
    refetchIntervalInBackground: true,
    // 開啟頁面／切回分頁一律重抓最新：全域 refetchOnWindowFocus=false（避免非即時查詢
    // 請求風暴），但即時報價必須覆寫——瀏覽器會把隱藏分頁的計時器節流到約每分鐘一次，
    // 不重抓的話切回來會先看到最多一分鐘前的舊價。
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<MoverRow[] | null>>(
        "/market/realtime/movers",
        { params: { type, limit } },
      );
      return res.data.data ?? null;
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

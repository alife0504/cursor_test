"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  CalendarEvent,
  HeatmapResponse,
  IntradayResponse,
  MarketOverview,
  MoverRow,
  RealtimeOverview,
  RealtimeQuote,
  RealtimeSnapshot,
} from "@/lib/api-types";

// Phase 16 § B / § L:大盤 / 漲跌排行 hooks(dashboard 用)
//   - useMarketOverview(market)
//   - useMarketMovers(type, market, limit)
//   - useRealtimeIndex() / useRealtimeStock(symbols) — 盤中即時報價（輪詢）

/** 台指期近月：data_id=TXF 回多個月份契約 + R1/R2 連續合約。
 *
 *  首選 `TXFR1`＝官方「近月連續合約」，結算日會自動換到新契約、零維護（R2=次近月）；
 *  取不到才退回「當日累計成交量最大者」（近月一定量最大）。
 *  ⚠️ 不可用 `volume` 挑：那是該筆撮合量，實測每個契約都是 1，等於挑到回傳順序第一筆
 *  （常是總量 1、時間停在數小時前的死遠月契約）。累計量要看 `total_volume`。
 *
 *  市場總覽與儀表板共用，避免兩處各自實作而走樣。 */
export function nearMonthFutures(
  snap?: RealtimeSnapshot,
): RealtimeQuote | null {
  if (!snap?.available || !snap.quotes?.length) return null;
  const r1 = snap.quotes.find((q) => q.symbol === "TXFR1");
  if (r1) return r1;
  return snap.quotes.reduce((best, q) =>
    (q.total_volume ?? 0) > (best.total_volume ?? 0) ? q : best,
  );
}

const TW_TIMEZONE = "Asia/Taipei";
/** 盤中輪詢間隔。後端有快照快取（TTL 2 秒），故上游用量與開幾個頁面無關。 */
export const REALTIME_POLL_MS = 5_000;

/**
 * 非交易時段的「心跳」間隔。
 *
 * ⚠️ 不可在收盤時直接回 false 停掉輪詢：React Query 只在**每次抓取之後**才重新計算
 * refetchInterval，一旦回 false 就再也不會重算 → 使用者 08:20 開著頁面，08:45 開盤時
 * 不會自動開始更新，要手動重整或切分頁回來才會醒。改為收盤時仍以 60 秒心跳輪詢：
 * 成本極低（且後端有快取），但能在開盤那一刻自動升回 5 秒即時。
 */
const CLOSED_HEARTBEAT_MS = 60_000;

/** 依交易時段給輪詢間隔：盤中 5 秒、收盤 60 秒心跳（用於自動偵測開盤）。 */
function sessionInterval(isOpen: boolean): number {
  return isOpen ? REALTIME_POLL_MS : CLOSED_HEARTBEAT_MS;
}

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

/** 即時大盤指數（加權 / 櫃買）。盤中每 5 秒更新；收盤改 60 秒心跳（開盤自動升回 5 秒）。 */
export function useRealtimeIndex(enabled = true) {
  return useQuery({
    queryKey: ["market", "realtime", "index"],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => sessionInterval(isTwMarketOpen()),
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
    refetchInterval: () => sessionInterval(isTwMarketOpen()),
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

/** 即時期貨報價（台指全，contract=台指期 TXF）。
 *  日盤 08:45–13:45 ＋夜盤 15:00–翌日 05:00 每 5 秒；非交易時段 60 秒心跳，
 *  開盤瞬間自動升回 5 秒。allDay=true 則一律 5 秒（除錯用，正常請維持 false）。 */
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
    refetchInterval: () => sessionInterval(allDay || isTwFuturesOpen()),
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

/** 即時大盤（漲跌家數/總量）。僅 TW；盤中每 5 秒、收盤 60 秒心跳。data 為 null 表即時不可用。 */
export function useRealtimeOverview(enabled = true) {
  return useQuery({
    queryKey: ["market", "realtime", "overview"],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => sessionInterval(isTwMarketOpen()),
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
    refetchInterval: () => sessionInterval(isTwMarketOpen()),
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

// 海外指數輪詢間隔。yfinance 本來就延遲 ~15 分，60 秒輪詢已遠比資料更新頻繁；
// 不看台股時段（海外市場各有各的交易時間，且期貨近 24 小時）。
const FOREIGN_POLL_MS = 60_000;

/** 海外指數延遲報價（道瓊期貨/那斯達克期貨/費半/韓國/日經）。60 秒輪詢、開頁必抓最新。 */
export function useRealtimeForeign(enabled = true) {
  return useQuery({
    queryKey: ["market", "realtime", "foreign"],
    enabled,
    staleTime: 30_000,
    refetchInterval: FOREIGN_POLL_MS,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RealtimeSnapshot>>(
        "/market/realtime/foreign",
      );
      return res.data.data;
    },
  });
}

/** 板塊熱力圖（產業→個股；每檔含即時漲跌%＋資金流億）。盤中 5 秒、收盤 60 秒心跳。 */
export function useHeatmap(enabled = true) {
  return useQuery({
    queryKey: ["market", "heatmap"],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () => sessionInterval(isTwMarketOpen()),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<HeatmapResponse>>("/market/heatmap");
      return res.data.data;
    },
  });
}

// 盤中即時走勢（加權指數 5 秒序列 / 台指全逐筆）。加權用日盤時段、台指全用期貨時段判斷輪詢。
export function useIntraday(symbol: "TAIEX" | "TXF", enabled = true) {
  return useQuery({
    queryKey: ["market", "intraday", symbol],
    enabled,
    staleTime: REALTIME_POLL_MS - 1_000,
    refetchInterval: () =>
      sessionInterval(symbol === "TXF" ? isTwFuturesOpen() : isTwMarketOpen()),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<IntradayResponse>>(
        `/market/intraday?symbol=${symbol}`,
      );
      return res.data.data;
    },
  });
}

// 盤後資料的「盤中兜底輪詢」間隔。即時層取不到時（未開通 / tier 不足 / 配額用盡）
// 畫面會退回這些盤後查詢；它們原本零輪詢 → 盤中整場凍結。給一個較保守的 30 秒輪詢，
// 讓退回路徑至少會動（盤後資料本來就不會每 5 秒變，30 秒足夠且不浪費）。
const EOD_FALLBACK_POLL_MS = 30_000;

export function useMarketOverview(market = "TW", enabled = true) {
  return useQuery({
    queryKey: ["market", "overview", market],
    enabled,
    staleTime: 60_000,
    refetchInterval: () => (isTwMarketOpen() ? EOD_FALLBACK_POLL_MS : false),
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
    // 同 useMarketOverview：即時榜取不到時的退回路徑，盤中至少 30 秒動一次
    refetchInterval: () => (isTwMarketOpen() ? EOD_FALLBACK_POLL_MS : false),
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

"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  AnnouncementItem,
  InstitutionalResponse,
  NewsItem,
} from "@/lib/api-types";

// Phase 17 § C / § L / § M:三大法人 + news / announcements
//   - 後端 P11 只有「個股」news 與 announcement,沒有全域聚合 endpoint
//   - 全域 view 採「個股聚合」做法:從 watchlist 拿 symbol → fan-out
//     單頁如要全域請改自選股 / symbol query

// ════════════════ Institutional ════════════════

export interface UseInstitutionalParams {
  market?: "TW" | "TPEX" | "US";
  date?: string | null;
  limit?: number;
  order?: "buy" | "sell"; // buy=外資買超最大 / sell=外資賣超最大
  enabled?: boolean;
}

export function useInstitutional(params: UseInstitutionalParams = {}) {
  const { market = "TW", date, limit = 100, order = "buy", enabled = true } = params;
  return useQuery({
    queryKey: ["market", "institutional", { market, date, limit, order }],
    enabled,
    staleTime: 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<InstitutionalResponse>>(
        "/market/institutional",
        { params: { market, date: date || undefined, limit, order } },
      );
      return res.data.data;
    },
  });
}

// ════════════════ News ════════════════
// 後端在 /stocks/{symbol}/news;個股查詢
export interface UseStockNewsParams {
  symbol: string;
  limit?: number;
  enabled?: boolean;
}

export function useStockNews({
  symbol,
  limit = 30,
  enabled = true,
}: UseStockNewsParams) {
  return useQuery({
    queryKey: ["news", "stock", symbol, limit],
    enabled: enabled && Boolean(symbol),
    staleTime: 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<NewsItem[]>>(
        `/stocks/${encodeURIComponent(symbol)}/news`,
        { params: { limit } },
      );
      return res.data.data ?? [];
    },
  });
}

// ════════════════ Announcements ════════════════
export interface UseStockAnnouncementsParams {
  symbol: string;
  limit?: number;
  enabled?: boolean;
}

export function useStockAnnouncements({
  symbol,
  limit = 30,
  enabled = true,
}: UseStockAnnouncementsParams) {
  return useQuery({
    queryKey: ["announcements", "stock", symbol, limit],
    enabled: enabled && Boolean(symbol),
    staleTime: 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AnnouncementItem[]>>(
        `/stocks/${encodeURIComponent(symbol)}/announcements`,
        { params: { limit } },
      );
      return res.data.data ?? [];
    },
  });
}

// ════════════════ Calendar (market 全域,P17 mock) ════════════════
export interface UseCalendarParams {
  from: string;
  to: string;
  market?: "TW" | "US";
  enabled?: boolean;
}

export function useCalendar({
  from,
  to,
  market = "TW",
  enabled = true,
}: UseCalendarParams) {
  return useQuery({
    queryKey: ["market", "calendar", { from, to, market }],
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<unknown[]>>("/market/calendar", {
        params: { from, to, market },
      });
      return res.data.data ?? [];
    },
  });
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  WatchlistCreateBody,
  WatchlistItem,
  WatchlistUpdateBody,
} from "@/lib/api-types";

// Phase 16 § C / § L:自選股 CRUD hooks
//   - useWatchlist():列表
//   - useAddWatchlist():POST /watchlist
//   - useUpdateWatchlist():PATCH /watchlist/{id}(inline edit note / sort)
//   - useDeleteWatchlist():DELETE

const WATCHLIST_KEY = ["watchlist"] as const;

export function useWatchlist(enabled = true) {
  return useQuery({
    queryKey: WATCHLIST_KEY,
    enabled,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<WatchlistItem[]>>("/watchlist");
      return res.data.data ?? [];
    },
  });
}

export function useAddWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: WatchlistCreateBody) => {
      const res = await api.post<ApiEnvelope<WatchlistItem>>("/watchlist", body);
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WATCHLIST_KEY });
    },
  });
}

export function useUpdateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id: string; body: WatchlistUpdateBody }) => {
      const res = await api.patch<ApiEnvelope<WatchlistItem>>(
        `/watchlist/${args.id}`,
        args.body,
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WATCHLIST_KEY });
    },
  });
}

export function useDeleteWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/watchlist/${id}`);
      return id;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WATCHLIST_KEY });
    },
  });
}

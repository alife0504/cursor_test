"use client";

import { QueryClient } from "@tanstack/react-query";

// Phase 15 § G:全域 React Query 設定
// - 不在 window focus refetch(避免每次切回分頁打爆 API)
// - 預設 30s staleTime + 1 次 retry
export const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        staleTime: 30_000,
        retry: 1,
      },
      mutations: {
        retry: 0,
      },
    },
  });

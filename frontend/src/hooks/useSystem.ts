"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { DLQItem, SystemInfo } from "@/lib/api-types";

// Phase 17 § O / § P:Admin 系統監控與資料管線
//   - GET /admin/system/info
//   - GET /admin/system/stats
//   - GET /admin/pipeline/dlq
//   - POST /admin/pipeline/dlq/{id}/resolve
//   - POST /admin/pipeline/dlq/{id}/requeue
// 註：舊有 useSystemMetrics（/admin/system/metrics）為死碼——全前端零引用，
// 且型別與後端 stub 回應不符，已移除避免未來誤用顯示 undefined。

export function useSystemInfo(enabled = true) {
  return useQuery({
    queryKey: ["admin", "system", "info"],
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<SystemInfo>>("/admin/system/info");
      return res.data.data;
    },
  });
}

// 即時系統統計（真值，非時序）：GET /admin/system/stats
export interface SystemStats {
  as_of: string;
  analyses_today: number;
  analyses_running: number;
  llm_cost_today_usd: number;
  llm_tokens_today: number;
  db_size_bytes: number;
  celery_queue_len: number | null;
}

export function useSystemStats(enabled = true) {
  return useQuery({
    queryKey: ["admin", "system", "stats"],
    enabled,
    refetchInterval: 15_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<SystemStats>>(
        "/admin/system/stats",
      );
      return res.data.data;
    },
  });
}

export interface UseDLQParams {
  resolved?: boolean | null;
  limit?: number;
  enabled?: boolean;
}

export function useDLQ(params: UseDLQParams = {}) {
  const { resolved = false, limit = 50, enabled = true } = params;
  return useQuery({
    queryKey: ["admin", "pipeline", "dlq", { resolved, limit }],
    enabled,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<DLQItem[]>>(
        "/admin/pipeline/dlq",
        {
          params: {
            resolved: resolved === null ? undefined : String(resolved),
            limit,
          },
        },
      );
      return res.data.data ?? [];
    },
  });
}

export interface ResolveDLQVars {
  id: number;
  notes: string;
}

export function useResolveDLQ() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, notes }: ResolveDLQVars) => {
      const res = await api.post<ApiEnvelope<DLQItem>>(
        `/admin/pipeline/dlq/${id}/resolve`,
        { notes },
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "pipeline", "dlq"] });
    },
  });
}

export function useRequeueDLQ() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.post<ApiEnvelope<DLQItem>>(
        `/admin/pipeline/dlq/${id}/requeue`,
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "pipeline", "dlq"] });
    },
  });
}

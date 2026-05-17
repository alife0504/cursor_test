"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { DLQItem, SystemInfo, SystemMetricsSummary } from "@/lib/api-types";

// Phase 17 § O / § P:Admin 系統監控與資料管線
//   - GET /admin/system/metrics
//   - GET /admin/system/info
//   - GET /admin/pipeline/dlq
//   - POST /admin/pipeline/dlq/{id}/resolve
//   - POST /admin/pipeline/dlq/{id}/requeue

export function useSystemMetrics(enabled = true) {
  return useQuery({
    queryKey: ["admin", "system", "metrics"],
    enabled,
    refetchInterval: 30_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<SystemMetricsSummary>>(
        "/admin/system/metrics",
      );
      return res.data.data;
    },
  });
}

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

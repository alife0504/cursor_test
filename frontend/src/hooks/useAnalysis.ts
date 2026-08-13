"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  AnalysisCreateBody,
  AnalysisCreateResponse,
  AnalysisDetail,
  AnalysisSummary,
  DebateMessage,
} from "@/lib/api-types";

// Phase 16 § D-G / § L:分析相關 hooks
//   - useAnalysisList(params):列表(cursor pagination)
//   - useAnalysisDetail(id, refetchInterval):詳情
//   - useAnalysisDebate(id):debate 訊息
//   - useCreateAnalysis():POST /analysis + Idempotency-Key
//   - useCancelAnalysis():取消

export interface UseAnalysisListParams {
  status?: string | null;
  symbol?: string | null;
  cursor?: string | null;
  limit?: number;
}

export function useAnalysisList(
  params: UseAnalysisListParams = {},
  enabled = true,
) {
  const { status, symbol, cursor, limit = 50 } = params;
  return useQuery({
    queryKey: ["analysis", "list", { status, symbol, cursor, limit }],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AnalysisSummary[]>>("/analysis", {
        params: {
          status: status || undefined,
          symbol: symbol || undefined,
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

export function useAnalysisDetail(
  id: string | null | undefined,
  refetchIntervalMs: number | false = false,
) {
  return useQuery({
    queryKey: ["analysis", id],
    enabled: !!id,
    refetchInterval: refetchIntervalMs,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AnalysisDetail>>(
        `/analysis/${id}`,
      );
      return res.data.data;
    },
  });
}

export function useAnalysisDebate(id: string | null | undefined) {
  return useQuery({
    queryKey: ["analysis", id, "debate"],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<DebateMessage[]>>(
        `/analysis/${id}/debate`,
      );
      return res.data.data ?? [];
    },
  });
}

export interface CreateAnalysisVars {
  body: AnalysisCreateBody;
  idempotencyKey: string;
}

export function useCreateAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: CreateAnalysisVars) => {
      const res = await api.post<ApiEnvelope<AnalysisCreateResponse>>(
        "/analysis",
        vars.body,
        { headers: { "Idempotency-Key": vars.idempotencyKey } },
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analysis", "list"] });
    },
  });
}

export function useCancelAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post<ApiEnvelope<{ analysis_id: string; status: string }>>(
        `/analysis/${id}/cancel`,
      );
      return res.data.data;
    },
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["analysis", id] });
      qc.invalidateQueries({ queryKey: ["analysis", "list"] });
    },
  });
}

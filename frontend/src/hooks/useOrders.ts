"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { OrderSummary } from "@/lib/api-types";

// Phase 16 § H / § L:訂單 hooks
//   - useOrders():列表
//   - useApproveOrder():核准(雙重確認 UI 由父層處理)
//   - useRejectOrder():拒絕

export interface UseOrdersParams {
  status?: string | null;
  cursor?: string | null;
  limit?: number;
}

export function useOrders(params: UseOrdersParams = {}, enabled = true) {
  const { status, cursor, limit = 50 } = params;
  return useQuery({
    queryKey: ["orders", { status, cursor, limit }],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<OrderSummary[]>>("/orders", {
        params: {
          status: status || undefined,
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

export interface ApproveOrderVars {
  id: string;
  notes?: string | null;
  expectedVersion?: number | null;
}

export function useApproveOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: ApproveOrderVars) => {
      const res = await api.post<ApiEnvelope<OrderSummary>>(
        `/orders/${vars.id}/approve`,
        {
          notes: vars.notes ?? null,
          expected_version: vars.expectedVersion ?? null,
        },
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export interface RejectOrderVars {
  id: string;
  reason: string;
  expectedVersion?: number | null;
}

export function useRejectOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: RejectOrderVars) => {
      const res = await api.post<ApiEnvelope<OrderSummary>>(
        `/orders/${vars.id}/reject`,
        {
          reason: vars.reason,
          expected_version: vars.expectedVersion ?? null,
        },
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

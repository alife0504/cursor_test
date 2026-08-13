"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { AuditLogItem } from "@/lib/api-types";

// Phase 16 § J / § L:Audit Log hooks(admin only)

export interface UseAuditParams {
  actor?: string | null;
  action?: string | null;
  entity?: string | null;
  from?: string | null;
  to?: string | null;
  cursor?: string | null;
  limit?: number;
}

export function useAuditLogs(params: UseAuditParams = {}, enabled = true) {
  const { actor, action, entity, from, to, cursor, limit = 50 } = params;
  return useQuery({
    queryKey: [
      "admin",
      "audit",
      { actor, action, entity, from, to, cursor, limit },
    ],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AuditLogItem[]>>("/admin/audit", {
        params: {
          actor: actor || undefined,
          action: action || undefined,
          entity: entity || undefined,
          from: from || undefined,
          to: to || undefined,
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

"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type { QuotaMe } from "@/lib/api-types";

// Phase 16 § B / § L:LLM 月配額 hook
//   - dashboard 顯示用量 progress bar
//   - 對應 backend GET /api/v1/users/me/quota

export function useMyQuota(enabled = true) {
  return useQuery({
    queryKey: ["users", "me", "quota"],
    enabled,
    staleTime: 60_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<QuotaMe>>("/users/me/quota");
      return res.data.data;
    },
  });
}

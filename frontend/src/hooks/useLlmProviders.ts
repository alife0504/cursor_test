"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";

export interface LlmProvidersInfo {
  available_providers: string[];
  default_provider: string;
  default_model: string;
}

/**
 * GET /analysis/llm-providers — 目前已配置金鑰、可實際使用的 LLM provider。
 *
 * 前端據此標示/禁用「無對應金鑰」的模型選項，避免使用者選了 GPT/Claude
 * 卻被 fallback chain 靜默降級為預設 Gemini 而不自知。
 */
export function useLlmProviders() {
  return useQuery({
    queryKey: ["analysis", "llm-providers"],
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<LlmProvidersInfo>>(
        "/analysis/llm-providers",
      );
      return res.data.data;
    },
  });
}

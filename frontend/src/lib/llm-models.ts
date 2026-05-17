// Phase 16:可選 LLM 模型對應 backend 的 LLM_PROVIDER_REGISTRY
//   - 對齊 backend/app/services/llm_providers/__init__.py
//   - 顯示 pricing 給用戶比較

export interface LLMModelOption {
  id: string;
  label: string;
  provider: "google" | "openai" | "anthropic";
  inputPricePer1m: number; // USD
  outputPricePer1m: number;
  description: string;
}

export const LLM_MODELS: LLMModelOption[] = [
  {
    id: "gemini-2.0-flash",
    label: "Gemini 2.0 Flash",
    provider: "google",
    inputPricePer1m: 0.075,
    outputPricePer1m: 0.3,
    description: "Google,最便宜,速度快(預設)",
  },
  {
    id: "gpt-4o-mini",
    label: "GPT-4o mini",
    provider: "openai",
    inputPricePer1m: 0.15,
    outputPricePer1m: 0.6,
    description: "OpenAI,中等品質與成本",
  },
  {
    id: "claude-haiku-3-5",
    label: "Claude Haiku 3.5",
    provider: "anthropic",
    inputPricePer1m: 0.8,
    outputPricePer1m: 4.0,
    description: "Anthropic,品質佳但較貴",
  },
];

/** 簡單預估:依 analyst 數量 x debate 輪數估算 USD;v1.0 概略值 */
export function estimateCostUsd(
  modelId: string,
  analystCount: number,
  debateRounds: number,
): { low: number; high: number } {
  const m = LLM_MODELS.find((x) => x.id === modelId);
  if (!m) return { low: 0, high: 0 };
  // 經驗值:每個 analyst 平均 5k token、debate 每輪 8k token、最後 manager 4k
  const tokens = analystCount * 5000 + debateRounds * 2 * 8000 + 4000;
  const cost = (tokens / 1_000_000) * (m.inputPricePer1m + m.outputPricePer1m);
  return { low: cost * 0.7, high: cost * 1.4 };
}

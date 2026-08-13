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
    id: "gemini-2.5-flash",
    label: "Gemini 2.5 Flash",
    provider: "google",
    inputPricePer1m: 0.3,
    outputPricePer1m: 2.5,
    description: "Google,品質佳,速度快(預設)",
  },
  {
    id: "gemini-2.5-flash-lite",
    label: "Gemini 2.5 Flash-Lite",
    provider: "google",
    inputPricePer1m: 0.1,
    outputPricePer1m: 0.4,
    description: "Google,最便宜,速度最快",
  },
  {
    id: "gemini-3.5-flash",
    label: "Gemini 3.5 Flash",
    provider: "google",
    inputPricePer1m: 0.3,
    outputPricePer1m: 2.5,
    description: "Google,最新(需 API 已開放)",
  },
  {
    id: "gemini-2.0-flash",
    label: "Gemini 2.0 Flash",
    provider: "google",
    inputPricePer1m: 0.075,
    outputPricePer1m: 0.3,
    description: "Google,上一代,便宜",
  },
  {
    id: "gpt-4o-mini",
    label: "GPT-4o mini",
    provider: "openai",
    inputPricePer1m: 0.15,
    outputPricePer1m: 0.6,
    description: "OpenAI,需有效金鑰",
  },
  {
    id: "claude-haiku-4-5",
    label: "Claude Haiku 4.5",
    provider: "anthropic",
    inputPricePer1m: 1.0,
    outputPricePer1m: 5.0,
    description: "Anthropic,快且便宜,需有效金鑰",
  },
  {
    id: "claude-sonnet-4-6",
    label: "Claude Sonnet 4.6",
    provider: "anthropic",
    inputPricePer1m: 3.0,
    outputPricePer1m: 15.0,
    description: "Anthropic,品質高,需有效金鑰",
  },
  {
    id: "claude-sonnet-5",
    label: "Claude Sonnet 5",
    provider: "anthropic",
    inputPricePer1m: 3.0,
    outputPricePer1m: 15.0,
    description: "Anthropic,現役 Sonnet,近 Opus 品質,需有效金鑰",
  },
  {
    id: "claude-opus-4-8",
    label: "Claude Opus 4.8",
    provider: "anthropic",
    inputPricePer1m: 5.0,
    outputPricePer1m: 25.0,
    description: "Anthropic,最強旗艦,最貴,需有效金鑰",
  },
];

/** 簡單預估:依 analyst 數量 x debate 輪數 x 風險輪數估算 USD;v1.0 概略值 */
export function estimateCostUsd(
  modelId: string,
  analystCount: number,
  debateRounds: number,
  riskRounds = 0,
): { low: number; high: number } {
  const m = LLM_MODELS.find((x) => x.id === modelId);
  if (!m) return { low: 0, high: 0 };
  // 經驗值:每個 analyst 平均 5k token、debate 每輪 8k token、最後 manager 4k
  let tokens = analystCount * 5000 + debateRounds * 2 * 8000 + 4000;
  // 完整風險架構(risk_rounds>0):交易員 3k + 每輪 3 位風險辯論員各 3k + 風險經理 4k
  if (riskRounds > 0) {
    tokens += 3000 + riskRounds * 3 * 3000 + 4000;
  }
  const cost = (tokens / 1_000_000) * (m.inputPricePer1m + m.outputPricePer1m);
  return { low: cost * 0.7, high: cost * 1.4 };
}

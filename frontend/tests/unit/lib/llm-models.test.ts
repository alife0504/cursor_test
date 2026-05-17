import { describe, expect, test } from "vitest";

import { LLM_MODELS, estimateCostUsd } from "@/lib/llm-models";

describe("LLM_MODELS", () => {
  test("至少包含 3 個模型(google / openai / anthropic)", () => {
    expect(LLM_MODELS.length).toBeGreaterThanOrEqual(3);
    const providers = new Set(LLM_MODELS.map((m) => m.provider));
    expect(providers.has("google")).toBe(true);
    expect(providers.has("openai")).toBe(true);
    expect(providers.has("anthropic")).toBe(true);
  });

  test("每個模型有合法 pricing", () => {
    for (const m of LLM_MODELS) {
      expect(m.inputPricePer1m).toBeGreaterThan(0);
      expect(m.outputPricePer1m).toBeGreaterThan(0);
      expect(m.id.length).toBeGreaterThan(0);
    }
  });
});

describe("estimateCostUsd", () => {
  test("未知模型回傳 0", () => {
    const r = estimateCostUsd("unknown", 2, 1);
    expect(r.low).toBe(0);
    expect(r.high).toBe(0);
  });

  test("低值小於高值", () => {
    const r = estimateCostUsd("gemini-2.0-flash", 3, 2);
    expect(r.low).toBeLessThanOrEqual(r.high);
    expect(r.high).toBeGreaterThan(0);
  });

  test("Claude Haiku 比 Gemini 貴", () => {
    const cheap = estimateCostUsd("gemini-2.0-flash", 2, 1);
    const expensive = estimateCostUsd("claude-haiku-3-5", 2, 1);
    expect(expensive.high).toBeGreaterThan(cheap.high);
  });

  test("更多 analyst → cost 增加", () => {
    const a = estimateCostUsd("gpt-4o-mini", 1, 0);
    const b = estimateCostUsd("gpt-4o-mini", 4, 0);
    expect(b.high).toBeGreaterThan(a.high);
  });

  test("更多 debate rounds → cost 增加", () => {
    const a = estimateCostUsd("gpt-4o-mini", 2, 0);
    const b = estimateCostUsd("gpt-4o-mini", 2, 3);
    expect(b.high).toBeGreaterThan(a.high);
  });
});

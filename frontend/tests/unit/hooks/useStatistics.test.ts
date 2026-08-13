import { describe, expect, test } from "vitest";

import {
  computeAccuracyFromAnalyses,
  computeModelStats,
} from "@/hooks/useStatistics";
import type { AnalysisSummary } from "@/lib/api-types";

function mk(
  o: Partial<AnalysisSummary> & { signal?: string; confidence?: string },
): AnalysisSummary {
  return {
    id: o.id ?? Math.random().toString(),
    symbol: o.symbol ?? "2330",
    market: "TWSE",
    status: "completed",
    signal: (o.signal as AnalysisSummary["signal"]) ?? null,
    confidence: o.confidence ?? null,
    llm_model: o.llm_model ?? "gemini-2.0-flash",
    total_cost_usd: o.total_cost_usd ?? "0.01",
    created_at: "2025-01-01T00:00:00Z",
    completed_at: null,
  };
}

describe("computeAccuracyFromAnalyses", () => {
  test("空輸入 → 0 命中率", () => {
    const s = computeAccuracyFromAnalyses([]);
    expect(s.total).toBe(0);
    expect(s.buy.rate).toBe(0);
    expect(s.sell.rate).toBe(0);
  });

  test("confidence >= 0.6 視為 hit", () => {
    const s = computeAccuracyFromAnalyses([
      mk({ signal: "BUY", confidence: "0.7" }),
      mk({ signal: "BUY", confidence: "0.5" }),
      mk({ signal: "SELL", confidence: "0.8" }),
    ]);
    expect(s.buy.total).toBe(2);
    expect(s.buy.hits).toBe(1);
    expect(s.buy.rate).toBeCloseTo(0.5);
    expect(s.sell.total).toBe(1);
    expect(s.sell.hits).toBe(1);
    expect(s.sell.rate).toBeCloseTo(1.0);
  });

  test("HOLD 不計入 BUY/SELL stats", () => {
    const s = computeAccuracyFromAnalyses([
      mk({ signal: "HOLD", confidence: "0.9" }),
    ]);
    expect(s.buy.total).toBe(0);
    expect(s.sell.total).toBe(0);
    expect(s.total).toBe(1);
  });
});

describe("computeModelStats", () => {
  test("group by llm_model + 計算平均成本", () => {
    const rows = [
      mk({ llm_model: "gemini-2.0-flash", total_cost_usd: "0.01" }),
      mk({ llm_model: "gemini-2.0-flash", total_cost_usd: "0.03" }),
      mk({ llm_model: "claude-opus-4", total_cost_usd: "0.20" }),
    ];
    const s = computeModelStats(rows);
    expect(s.length).toBe(2);
    const gem = s.find((x) => x.model === "gemini-2.0-flash")!;
    expect(gem.total).toBe(2);
    expect(gem.total_cost_usd).toBeCloseTo(0.04);
    expect(gem.avg_cost_usd).toBeCloseTo(0.02);
    const cla = s.find((x) => x.model === "claude-opus-4")!;
    expect(cla.total).toBe(1);
    expect(cla.avg_cost_usd).toBeCloseTo(0.2);
  });

  test("依 total 降序排序", () => {
    const rows = [
      mk({ llm_model: "a" }),
      mk({ llm_model: "b" }),
      mk({ llm_model: "b" }),
      mk({ llm_model: "b" }),
    ];
    const s = computeModelStats(rows);
    expect(s[0].model).toBe("b");
  });
});

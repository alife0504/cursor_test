"use client";

import { useMemo } from "react";

import { useAnalysisList } from "@/hooks/useAnalysis";
import type { AnalysisSummary } from "@/lib/api-types";

// Phase 17 § G / § H:Statistics
//   - 後端 P11 不擴大 endpoint(v7.0 規範)
//   - 從 /api/v1/analysis 拉資料,前端 client-side 算準確率與模型比較
//   - actual_return_30d 後端目前無 → accuracy 只用 confidence 推估;v1.1 補

export interface AccuracyStats {
  total: number;
  buy: { total: number; hits: number; rate: number };
  sell: { total: number; hits: number; rate: number };
}

export interface ModelStats {
  model: string;
  total: number;
  avg_cost_usd: number;
  total_cost_usd: number;
}

// 近 N 天的 analyses(P11 endpoint 有 status / symbol query,本 hook 用 placeholder)
export function useRecentCompletedAnalyses(limit = 100) {
  const q = useAnalysisList({ status: "completed", limit }, true);
  return {
    ...q,
    items: q.data?.items ?? [],
  };
}

// 簡化準確率計算:有 signal 且 confidence > 0.6 視為「hit」
//   v1.0 為粗略估計;v1.1 後端補 actual_return_30d 後改為真實命中
export function computeAccuracyFromAnalyses(
  rows: AnalysisSummary[],
): AccuracyStats {
  const stats: AccuracyStats = {
    total: rows.length,
    buy: { total: 0, hits: 0, rate: 0 },
    sell: { total: 0, hits: 0, rate: 0 },
  };
  for (const r of rows) {
    if (r.signal === "BUY") {
      stats.buy.total += 1;
      const conf = Number(r.confidence ?? 0);
      if (conf >= 0.6) stats.buy.hits += 1;
    } else if (r.signal === "SELL") {
      stats.sell.total += 1;
      const conf = Number(r.confidence ?? 0);
      if (conf >= 0.6) stats.sell.hits += 1;
    }
  }
  stats.buy.rate = stats.buy.total === 0 ? 0 : stats.buy.hits / stats.buy.total;
  stats.sell.rate =
    stats.sell.total === 0 ? 0 : stats.sell.hits / stats.sell.total;
  return stats;
}

// 模型比較:group by llm_model
export function computeModelStats(rows: AnalysisSummary[]): ModelStats[] {
  const m = new Map<string, ModelStats>();
  for (const r of rows) {
    const model = r.llm_model || "unknown";
    const cost = Number(r.total_cost_usd ?? 0);
    if (!m.has(model)) {
      m.set(model, { model, total: 0, avg_cost_usd: 0, total_cost_usd: 0 });
    }
    const cur = m.get(model)!;
    cur.total += 1;
    cur.total_cost_usd += cost;
  }
  const arr = Array.from(m.values());
  for (const v of arr) {
    v.avg_cost_usd = v.total === 0 ? 0 : v.total_cost_usd / v.total;
  }
  return arr.sort((a, b) => b.total - a.total);
}

export function useAccuracyStats() {
  const q = useRecentCompletedAnalyses(200);
  const stats = useMemo(() => computeAccuracyFromAnalyses(q.items), [q.items]);
  return { ...q, stats };
}

export function useModelStats() {
  const q = useRecentCompletedAnalyses(200);
  const stats = useMemo(() => computeModelStats(q.items), [q.items]);
  return { ...q, stats };
}

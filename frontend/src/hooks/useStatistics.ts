"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAnalysisList } from "@/hooks/useAnalysis";
import { api, type ApiEnvelope } from "@/lib/api";
import type { AnalysisSummary } from "@/lib/api-types";

// Phase 17 § G / § H:Statistics
//   - 模型比較：從 /api/v1/analysis 拉資料，前端 client-side group by 模型（真實）
//   - 準確率（v1.1）：改用後端 /api/v1/statistics/accuracy，
//     以「分析建立之後 N 日實際報酬」計算真實命中率（PIT 正確），取代舊 confidence 粗估

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

// ── v1.1 真實命中率（後端 PIT 計算）────────────────────────────────

export type AccuracyRowStatus = "scored" | "pending" | "no_data";

export interface AccuracyRow {
  id: string;
  symbol: string;
  signal: "BUY" | "SELL";
  confidence: number | null;
  created_at: string;
  horizon_days: number;
  entry_date: string | null;
  entry_price: number | null;
  exit_date: string | null;
  exit_price: number | null;
  actual_return: number | null; // 小數（0.1 = +10%）
  hit: boolean | null;
  status: AccuracyRowStatus;
}

export interface AccuracySide {
  scored: number;
  hits: number;
  hit_rate: number; // 0..1
  avg_return: number; // 小數
}

export interface AccuracyResponse {
  horizon_days: number;
  overall: { scored: number; hits: number; hit_rate: number };
  buy: AccuracySide;
  sell: AccuracySide;
  pending: number;
  no_data: number;
  rows: AccuracyRow[];
}

const EMPTY_ACCURACY: AccuracyResponse = {
  horizon_days: 30,
  overall: { scored: 0, hits: 0, hit_rate: 0 },
  buy: { scored: 0, hits: 0, hit_rate: 0, avg_return: 0 },
  sell: { scored: 0, hits: 0, hit_rate: 0, avg_return: 0 },
  pending: 0,
  no_data: 0,
  rows: [],
};

// 真實命中率：signal 對上「分析建立之後」N 日實際報酬（後端 user-scoped、PIT 正確）
export function useAccuracyStats(horizonDays = 30, lookbackDays = 180) {
  const q = useQuery({
    queryKey: ["statistics", "accuracy", { horizonDays, lookbackDays }],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AccuracyResponse>>(
        "/statistics/accuracy",
        { params: { horizon_days: horizonDays, lookback_days: lookbackDays } },
      );
      return res.data.data ?? EMPTY_ACCURACY;
    },
  });
  return {
    ...q,
    stats: q.data ?? EMPTY_ACCURACY,
    rows: q.data?.rows ?? [],
  };
}

// ── v1.1 真實回測（後端策略引擎，PIT 正確）──────────────────────

export interface BacktestPoint {
  date: string;
  equity: number;
  drawdown: number;
}

export interface BacktestMetrics {
  total_return: number;
  annualized_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  num_trades: number;
}

export interface BacktestResponse {
  symbol: string;
  strategy: string;
  period: string;
  start_date: string;
  end_date: string;
  trading_days: number;
  initial_capital: number;
  curve: BacktestPoint[];
  metrics: BacktestMetrics;
  benchmark_curve: Array<{ date: string; equity: number }>;
  benchmark_metrics: BacktestMetrics;
  error?: string;
}

// 策略回測：對歷史日 K 跑策略（後端 PIT 引擎），附 Buy&Hold 基準
export function useBacktest(
  symbol: string | null,
  strategy: string,
  period: string,
) {
  return useQuery({
    queryKey: ["statistics", "backtest", { symbol, strategy, period }],
    enabled: !!symbol,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<BacktestResponse>>(
        "/statistics/backtest",
        { params: { symbol, strategy, period } },
      );
      return res.data.data;
    },
  });
}

export function useModelStats() {
  const q = useRecentCompletedAnalyses(200);
  const stats = useMemo(() => computeModelStats(q.items), [q.items]);
  return { ...q, stats };
}

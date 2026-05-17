"use client";

import { useMemo } from "react";

import { BarChart } from "@/components/common/BarChart";
import { ChartContainer } from "@/components/common/ChartContainer";
import type { NewsItem } from "@/lib/api-types";

// Phase 17 § L:新聞情緒分佈 bar chart
//   - 5 級:極正 / 正 / 中 / 負 / 極負
//   - 從 sentiment_label 累加

const ORDER = [
  "very_positive",
  "positive",
  "neutral",
  "negative",
  "very_negative",
] as const;

const LABELS: Record<(typeof ORDER)[number], string> = {
  very_positive: "極正面",
  positive: "正面",
  neutral: "中性",
  negative: "負面",
  very_negative: "極負面",
};

const COLORS: Record<(typeof ORDER)[number], string> = {
  very_positive: "#16a34a",
  positive: "#84cc16",
  neutral: "#a3a3a3",
  negative: "#f97316",
  very_negative: "#dc2626",
};

export function SentimentBar({ items }: { items: NewsItem[] }) {
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const l of ORDER) c[l] = 0;
    for (const it of items) {
      const lbl = (it.sentiment_label ?? "neutral") as string;
      if (lbl in c) c[lbl] += 1;
    }
    return ORDER.map((l) => ({
      sentiment: LABELS[l],
      count: c[l],
      fill: COLORS[l],
    }));
  }, [items]);

  return (
    <ChartContainer title="情緒分佈" height={220}>
      <BarChart
        data={counts}
        xKey="sentiment"
        series={[{ dataKey: "count", name: "篇數" }]}
        showLegend={false}
      />
    </ChartContainer>
  );
}

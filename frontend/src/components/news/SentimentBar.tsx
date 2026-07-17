"use client";

import { useMemo } from "react";

import { BarChart } from "@/components/common/BarChart";
import { ChartContainer } from "@/components/common/ChartContainer";
import type { NewsItem } from "@/lib/api-types";

// Phase 17 § L:新聞情緒分佈 bar chart
//   - 5 級:極正 / 正 / 中 / 負 / 極負
//   - 從 sentiment_label 累加

const ORDER = [
  "positive",
  "neutral",
  "negative",
  "unknown",
] as const;

// DB 實際只有 positive/neutral/negative/unknown 四值（非 5 級）。原本用 5 級 +
// 忽略 unknown → 未評級新聞全被丟棄、分佈圖恆空。改對齊實際值。
const LABELS: Record<(typeof ORDER)[number], string> = {
  positive: "正面",
  neutral: "中性",
  negative: "負面",
  unknown: "未評級",
};

// 台股慣例：紅=正面(利多/bull)、綠=負面(利空/bear)，與右側情緒表格 SENTIMENT_LABEL_MAP 一致。
// 用設計 token（hsl var）而非硬編碼 hex，才會隨深色模式調整、且不與全站「紅漲綠跌」相矛盾。
const COLORS: Record<(typeof ORDER)[number], string> = {
  positive: "hsl(var(--bull))",
  neutral: "hsl(var(--flat))",
  negative: "hsl(var(--bear))",
  unknown: "hsl(var(--muted-foreground) / 0.4)",
};

export function SentimentBar({ items }: { items: NewsItem[] }) {
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const l of ORDER) c[l] = 0;
    for (const it of items) {
      const lbl = (it.sentiment ?? it.sentiment_label ?? "unknown") as string;
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

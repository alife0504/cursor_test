"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";

// 折線/面積圖 wrapper（回測權益曲線、回撤）
//   - dynamic import 避免 SSR（recharts 用 window）
//   - 高度由父層 ChartContainer 控制

export interface LineSeries {
  dataKey: string;
  name?: string;
  color?: string; // CSS 色（預設由 palette 依序）
  area?: boolean; // true → 填色面積
}

export interface LineChartProps {
  data: Array<Record<string, unknown>>;
  series: LineSeries[];
  xKey: string;
  className?: string;
  emptyText?: ReactNode;
  showLegend?: boolean;
  yTickFormatter?: (v: number) => string;
  xTickFormatter?: (v: string) => string;
}

const DynamicLineChart = dynamic(
  () => import("./LineChartInner").then((m) => m.LineChartInner),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        載入圖表中…
      </div>
    ),
  },
);

export function LineChart(props: LineChartProps) {
  if (!props.data.length) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {props.emptyText ?? "尚無資料"}
      </div>
    );
  }
  return <DynamicLineChart {...props} />;
}

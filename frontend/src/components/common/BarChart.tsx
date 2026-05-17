"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";

// Phase 17 § R:recharts BarChart wrapper
//   - 整個 chart 元件 dynamic import 避免 SSR 報錯(recharts 用 window 計算 ResponsiveContainer)
//   - 高度由父層 ChartContainer 控制

export interface BarSeries {
  dataKey: string;
  name?: string;
  fill?: string;
}

export interface BarChartProps {
  data: Array<Record<string, unknown>>;
  series: BarSeries[];
  xKey: string;
  className?: string;
  emptyText?: ReactNode;
  showLegend?: boolean;
}

const DynamicBarChart = dynamic(
  () => import("./BarChartInner").then((m) => m.BarChartInner),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        載入圖表中…
      </div>
    ),
  },
);

export function BarChart(props: BarChartProps) {
  if (!props.data.length) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {props.emptyText ?? "尚無資料"}
      </div>
    );
  }
  return <DynamicBarChart {...props} />;
}

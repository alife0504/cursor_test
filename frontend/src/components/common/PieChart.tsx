"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";

// Phase 17 § R:recharts PieChart wrapper

export interface PieDataItem {
  name: string;
  value: number;
  fill?: string;
}

export interface PieChartProps {
  data: PieDataItem[];
  className?: string;
  emptyText?: ReactNode;
  showLegend?: boolean;
  innerRadius?: number;
  outerRadius?: number;
}

const DynamicPieChart = dynamic(
  () => import("./PieChartInner").then((m) => m.PieChartInner),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        載入圖表中…
      </div>
    ),
  },
);

export function PieChart(props: PieChartProps) {
  if (!props.data.length || props.data.every((d) => d.value === 0)) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {props.emptyText ?? "尚無資料"}
      </div>
    );
  }
  return <DynamicPieChart {...props} />;
}

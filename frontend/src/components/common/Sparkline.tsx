"use client";

import dynamic from "next/dynamic";

import { cn } from "@/lib/utils";

const SparklineInner = dynamic(
  () => import("./SparklineInner").then((m) => m.SparklineInner),
  { ssr: false, loading: () => <div className="h-full w-full" /> },
);

interface SparklineProps {
  /** 一維數值序列；長度建議 5+ */
  data: Array<number | string | null | undefined>;
  /** 漲跌方向（自動以最後值 - 第一值；可外部覆寫） */
  tone?: "bull" | "bear" | "flat";
  className?: string;
  height?: number;
  /** 是否顯示底部 baseline；預設 false（純線） */
  showBaseline?: boolean;
}

export function Sparkline({
  data,
  tone,
  className,
  height = 48,
  showBaseline = false,
}: SparklineProps) {
  return (
    <div
      className={cn("w-full", className)}
      style={{ height }}
      aria-hidden="true"
      data-testid="sparkline"
    >
      <SparklineInner data={data} tone={tone} showBaseline={showBaseline} />
    </div>
  );
}

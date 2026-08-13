"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";

interface SparklineInnerProps {
  data: Array<number | string | null | undefined>;
  tone?: "bull" | "bear" | "flat";
  showBaseline?: boolean;
}

function toNum(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function autoTone(nums: number[]): "bull" | "bear" | "flat" {
  if (nums.length < 2) return "flat";
  const first = nums[0];
  const last = nums[nums.length - 1];
  if (first === last) return "flat";
  return last > first ? "bull" : "bear";
}

export function SparklineInner({
  data,
  tone,
  showBaseline,
}: SparklineInnerProps) {
  const cleaned = data
    .map((d) => toNum(d))
    .filter((v): v is number => v !== null);

  if (cleaned.length < 2) {
    return null;
  }

  const finalTone = tone ?? autoTone(cleaned);
  const stroke =
    finalTone === "bull"
      ? "hsl(var(--bull))"
      : finalTone === "bear"
        ? "hsl(var(--bear))"
        : "hsl(var(--flat))";
  const fill =
    finalTone === "bull"
      ? "hsl(var(--bull) / 0.18)"
      : finalTone === "bear"
        ? "hsl(var(--bear) / 0.18)"
        : "hsl(var(--flat) / 0.12)";

  const chartData = cleaned.map((v, i) => ({ i, v }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart
        data={chartData}
        margin={{ top: 2, right: 2, bottom: showBaseline ? 0 : 2, left: 2 }}
      >
        <defs>
          <linearGradient id="sparkline-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.3} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={stroke}
          strokeWidth={1.5}
          fill={fill}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

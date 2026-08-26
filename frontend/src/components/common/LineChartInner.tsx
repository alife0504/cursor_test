"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";

import type { LineChartProps } from "./LineChart";

const DEFAULT_COLORS = ["#3b82f6", "#94a3b8", "#f59e0b", "#ef4444", "#8b5cf6"];

export function LineChartInner({
  data,
  series,
  xKey,
  className,
  showLegend = true,
  yTickFormatter,
  xTickFormatter,
}: LineChartProps) {
  return (
    <div className={cn("h-full w-full", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey={xKey}
            fontSize={11}
            minTickGap={40}
            tickFormatter={xTickFormatter}
          />
          <YAxis
            fontSize={11}
            width={56}
            domain={["auto", "auto"]}
            tickFormatter={yTickFormatter}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(v: number) =>
              yTickFormatter ? yTickFormatter(v) : v.toLocaleString()
            }
          />
          {showLegend && <Legend />}
          {series.map((s, i) => {
            const color = s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length];
            return s.area ? (
              <Area
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name ?? s.dataKey}
                stroke={color}
                fill={color}
                fillOpacity={0.15}
                strokeWidth={1.5}
                dot={false}
              />
            ) : (
              <Line
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name ?? s.dataKey}
                stroke={color}
                strokeWidth={1.8}
                dot={false}
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

"use client";

import {
  Cell,
  Legend,
  Pie,
  PieChart as RePieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { cn } from "@/lib/utils";

import type { PieChartProps } from "./PieChart";

const DEFAULT_COLORS = [
  "#22c55e",
  "#84cc16",
  "#a3a3a3",
  "#f59e0b",
  "#ef4444",
  "#3b82f6",
  "#8b5cf6",
];

export function PieChartInner({
  data,
  className,
  showLegend = true,
  innerRadius = 0,
  outerRadius = 90,
}: PieChartProps) {
  return (
    <div className={cn("h-full w-full", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <RePieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            labelLine={false}
          >
            {data.map((entry, idx) => (
              <Cell
                key={entry.name}
                fill={entry.fill ?? DEFAULT_COLORS[idx % DEFAULT_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
        </RePieChart>
      </ResponsiveContainer>
    </div>
  );
}

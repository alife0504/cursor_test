"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BarChart } from "@/components/common/BarChart";
import { ChartContainer } from "@/components/common/ChartContainer";
import { DataTable } from "@/components/common/DataTable";
import { NumberFormat } from "@/components/common/NumberFormat";
import { useModelStats, type ModelStats } from "@/hooks/useStatistics";

// Phase 17 § H:模型比較
//   - client-side 從 /api/v1/analysis 聚合(P17 不擴大後端)
//   - 表格 + bar chart

export default function StatisticsModelsPage() {
  const { stats, isLoading } = useModelStats();

  const columns = useMemo<ColumnDef<ModelStats>[]>(
    () => [
      {
        accessorKey: "model",
        header: "模型",
        cell: ({ row }) => <code className="text-xs">{row.original.model}</code>,
      },
      {
        accessorKey: "total",
        header: "分析次數",
        cell: ({ row }) => <NumberFormat value={row.original.total} />,
      },
      {
        accessorKey: "avg_cost_usd",
        header: "平均成本 (USD)",
        cell: ({ row }) => (
          <NumberFormat value={row.original.avg_cost_usd} decimals={4} />
        ),
      },
      {
        accessorKey: "total_cost_usd",
        header: "累計成本 (USD)",
        cell: ({ row }) => (
          <NumberFormat value={row.original.total_cost_usd} decimals={4} />
        ),
      },
    ],
    [],
  );

  const chartData = useMemo(
    () =>
      stats.map((s) => ({
        model: s.model,
        total: s.total,
        avg_cost: s.avg_cost_usd,
      })),
    [stats],
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">模型比較</h1>
        <p className="text-sm text-muted-foreground">
          各 LLM 模型使用次數與平均成本(client-side 聚合)
        </p>
      </div>

      <ChartContainer title="模型使用分佈" height={260}>
        <BarChart
          data={chartData}
          xKey="model"
          series={[{ dataKey: "total", name: "次數" }]}
          showLegend={false}
        />
      </ChartContainer>

      <DataTable
        columns={columns}
        data={stats}
        isLoading={isLoading}
        emptyText="尚無模型使用記錄"
      />
    </div>
  );
}

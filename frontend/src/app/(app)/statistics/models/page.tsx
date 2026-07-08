"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Activity, Coins, Cpu, Sigma } from "lucide-react";
import { useMemo } from "react";

import { BarChart } from "@/components/common/BarChart";
import { ChartContainer } from "@/components/common/ChartContainer";
import { DataTable } from "@/components/common/DataTable";
import { KpiCard } from "@/components/common/KpiCard";
import { NumberFormat } from "@/components/common/NumberFormat";
import { PageHeader } from "@/components/common/PageHeader";
import { useModelStats, type ModelStats } from "@/hooks/useStatistics";

// Phase 17 § H:模型比較
//   - client-side 從 /api/v1/analysis 聚合(P17 不擴大後端)
//   - 表格 + bar chart

export default function StatisticsModelsPage() {
  const { stats, isLoading } = useModelStats();

  const summary = useMemo(() => {
    const totalRuns = stats.reduce((a, s) => a + Number(s.total ?? 0), 0);
    const totalCost = stats.reduce((a, s) => a + Number(s.total_cost_usd ?? 0), 0);
    return {
      models: stats.length,
      totalRuns,
      totalCost,
      avgCost: totalRuns > 0 ? totalCost / totalRuns : 0,
    };
  }, [stats]);

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
      <PageHeader
        icon={Cpu}
        title="模型比較"
        description="各 LLM 模型使用次數與平均成本（client-side 聚合）"
      />

      {/* 摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="使用模型數"
          value={summary.models}
          subtitle="不同 LLM 模型"
          icon={Cpu}
          accent="primary"
        />
        <KpiCard
          title="總分析次數"
          value={summary.totalRuns}
          subtitle="所有模型合計"
          icon={Activity}
          accent="info"
        />
        <KpiCard
          title="累計成本"
          value={`US$${summary.totalCost.toFixed(3)}`}
          subtitle="LLM 推論總費用"
          icon={Coins}
          accent="info"
        />
        <KpiCard
          title="平均每次成本"
          value={`US$${summary.avgCost.toFixed(4)}`}
          subtitle="總成本 / 總次數"
          icon={Sigma}
          accent="warning"
        />
      </section>

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

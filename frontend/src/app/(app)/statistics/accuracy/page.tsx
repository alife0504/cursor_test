"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { ChartContainer } from "@/components/common/ChartContainer";
import { DataTable } from "@/components/common/DataTable";
import { MockBanner } from "@/components/common/MockBanner";
import { PercentFormat } from "@/components/common/PercentFormat";
import { PieChart } from "@/components/common/PieChart";
import { SignalBadge } from "@/components/common/SignalBadge";
import { useAccuracyStats } from "@/hooks/useStatistics";
import type { AnalysisSummary } from "@/lib/api-types";

// Phase 17 § G:準確率分析
//   - v1.0 用 confidence>=0.6 視為「hit」(粗略估計,標 Mock)
//   - v1.1 後端補 actual_return_30d 後改為真實命中

export default function StatisticsAccuracyPage() {
  const { items, stats, isLoading } = useAccuracyStats();

  const columns = useMemo<ColumnDef<AnalysisSummary>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "建立時間",
        cell: ({ row }) => (
          <span className="text-xs tabular-nums">
            {row.original.created_at?.slice(0, 16)}
          </span>
        ),
      },
      {
        accessorKey: "symbol",
        header: "代號",
        cell: ({ row }) => (
          <Link
            href={`/analysis/${row.original.id}`}
            className="font-mono text-primary hover:underline"
          >
            {row.original.symbol}
          </Link>
        ),
      },
      {
        accessorKey: "signal",
        header: "訊號",
        cell: ({ row }) => (
          <SignalBadge
            signal={row.original.signal ?? null}
            status={row.original.status}
          />
        ),
      },
      {
        accessorKey: "confidence",
        header: "信心",
        cell: ({ row }) => (
          <PercentFormat value={row.original.confidence ?? null} colored />
        ),
      },
      {
        accessorKey: "llm_model",
        header: "模型",
        cell: ({ row }) => row.original.llm_model ?? "-",
      },
    ],
    [],
  );

  const pieData = [
    { name: "BUY 命中", value: stats.buy.hits, fill: "#22c55e" },
    { name: "BUY 失誤", value: stats.buy.total - stats.buy.hits, fill: "#86efac" },
    { name: "SELL 命中", value: stats.sell.hits, fill: "#ef4444" },
    { name: "SELL 失誤", value: stats.sell.total - stats.sell.hits, fill: "#fca5a5" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">準確率分析</h1>
        <p className="text-sm text-muted-foreground">
          已完成分析的訊號統計(client-side 計算)
        </p>
      </div>

      <MockBanner
        title="Mock 計算 - v1.1 將以 actual_return_30d 改為真實命中率"
        trackingRef="後端待補 endpoint:GET /api/v1/analysis/{id}/actual-return"
      />

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground">總分析數</p>
          <p className="text-2xl font-bold tabular-nums">{stats.total}</p>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground">BUY 命中率(粗估)</p>
          <p className="text-2xl font-bold tabular-nums text-emerald-600">
            <PercentFormat value={stats.buy.rate * 100} />
          </p>
          <p className="text-xs text-muted-foreground">
            {stats.buy.hits} / {stats.buy.total}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground">SELL 命中率(粗估)</p>
          <p className="text-2xl font-bold tabular-nums text-rose-600">
            <PercentFormat value={stats.sell.rate * 100} />
          </p>
          <p className="text-xs text-muted-foreground">
            {stats.sell.hits} / {stats.sell.total}
          </p>
        </div>
      </section>

      <ChartContainer title="訊號分佈" height={260}>
        <PieChart data={pieData} />
      </ChartContainer>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">分析記錄</h3>
        <DataTable
          columns={columns}
          data={items}
          isLoading={isLoading}
          emptyText="尚無已完成分析"
        />
      </section>
    </div>
  );
}

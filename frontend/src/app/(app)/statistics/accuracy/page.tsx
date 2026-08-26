"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { TrendingUp } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ChartContainer } from "@/components/common/ChartContainer";
import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { PageHeader } from "@/components/common/PageHeader";
import { PercentFormat } from "@/components/common/PercentFormat";
import { PieChart } from "@/components/common/PieChart";
import { SignalBadge } from "@/components/common/SignalBadge";
import { type AccuracyRow, useAccuracyStats } from "@/hooks/useStatistics";

// Phase 17 § G（v1.1）：真實準確率
//   - 後端 /api/v1/statistics/accuracy 以「分析建立之後 N 日實際報酬」計命中率（PIT 正確）
//   - BUY 命中＝報酬>0；SELL 命中＝報酬<0；視窗未過完 → 待計分（pending，不硬湊）

function HitCell({ row }: { row: AccuracyRow }) {
  if (row.status === "pending")
    return <span className="text-xs text-muted-foreground">待計分</span>;
  if (row.status === "no_data")
    return <span className="text-xs text-muted-foreground">無資料</span>;
  return row.hit ? (
    <span className="font-medium text-bull">✓ 命中</span>
  ) : (
    <span className="font-medium text-bear">✗ 失誤</span>
  );
}

const HORIZON_OPTIONS = [5, 10, 20, 30] as const;

export default function StatisticsAccuracyPage() {
  // 預設 5 日：資料還很新時，長天期視窗尚未過完（全待計分）；短天期今天即可計分。
  // 隨著歷史累積，可切到 20/30 日看更穩健的命中率。
  const [horizon, setHorizon] = useState<number>(5);
  const { stats, rows, isLoading, isError } = useAccuracyStats(horizon);

  const columns = useMemo<ColumnDef<AccuracyRow>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "建立時間",
        cell: ({ row }) => (
          <span className="text-xs tabular-nums">
            <DateFormat value={row.original.created_at} mode="datetime" />
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
          <SignalBadge signal={row.original.signal} status="completed" />
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
        accessorKey: "actual_return",
        header: `實際報酬（${horizon}日）`,
        cell: ({ row }) =>
          row.original.actual_return === null ? (
            <span className="text-xs text-muted-foreground">—</span>
          ) : (
            <PercentFormat value={row.original.actual_return} colored />
          ),
      },
      {
        id: "hit",
        header: "命中",
        cell: ({ row }) => <HitCell row={row.original} />,
      },
    ],
    [horizon],
  );

  // 紅漲綠跌：BUY=bull、SELL=bear（僅計已計分者）
  const pieData = [
    { name: "BUY 命中", value: stats.buy.hits, fill: "hsl(var(--bull))" },
    {
      name: "BUY 失誤",
      value: stats.buy.scored - stats.buy.hits,
      fill: "hsl(var(--bull) / 0.35)",
    },
    { name: "SELL 命中", value: stats.sell.hits, fill: "hsl(var(--bear))" },
    {
      name: "SELL 失誤",
      value: stats.sell.scored - stats.sell.hits,
      fill: "hsl(var(--bear) / 0.35)",
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={TrendingUp}
        title="準確率分析"
        description={`真實命中率：訊號對上「分析建立之後 ${horizon} 日」的實際報酬（含息、PIT 正確）`}
      />

      {isError ? (
        <p className="rounded-md border border-bear/30 bg-bear/5 p-3 text-xs text-bear">
          無法載入準確率資料，請稍後重試或確認已登入。
        </p>
      ) : null}

      <p className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
        方法：進場＝決策日收盤，出場＝{horizon} 日後收盤（未還原收盤，除息跳空計入）。
        BUY 命中＝報酬 &gt; 0、SELL 命中＝報酬 &lt; 0。
        <span className="text-foreground">
          {" "}
          報酬視窗尚未過完者標「待計分」，不納入命中率
        </span>
        （避免偷看未來）。僅統計你自己的已完成分析。
      </p>

      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">持有期</span>
        <div className="inline-flex rounded-md border p-0.5">
          {HORIZON_OPTIONS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHorizon(h)}
              className={
                horizon === h
                  ? "rounded px-3 py-1 text-xs font-medium bg-primary text-primary-foreground"
                  : "rounded px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
              }
            >
              {h} 日
            </button>
          ))}
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">總命中率</p>
          <p className="num text-2xl font-bold">
            <PercentFormat value={stats.overall.hit_rate} />
          </p>
          <p className="text-xs text-muted-foreground">
            {stats.overall.hits} / {stats.overall.scored} 已計分
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">BUY 命中率</p>
          <p className="num text-2xl font-bold text-bull">
            <PercentFormat value={stats.buy.hit_rate} />
          </p>
          <p className="text-xs text-muted-foreground">
            {stats.buy.hits} / {stats.buy.scored}　平均{" "}
            <PercentFormat value={stats.buy.avg_return} colored />
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">SELL 命中率</p>
          <p className="num text-2xl font-bold text-bear">
            <PercentFormat value={stats.sell.hit_rate} />
          </p>
          <p className="text-xs text-muted-foreground">
            {stats.sell.hits} / {stats.sell.scored}　平均{" "}
            <PercentFormat value={stats.sell.avg_return} colored />
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">待計分</p>
          <p className="num text-2xl font-bold">{stats.pending}</p>
          <p className="text-xs text-muted-foreground">
            視窗未滿 {horizon} 日{stats.no_data ? `／無資料 ${stats.no_data}` : ""}
          </p>
        </div>
      </section>

      <ChartContainer title="訊號分佈（已計分）" height={260}>
        <PieChart data={pieData} />
      </ChartContainer>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">分析記錄</h3>
        <DataTable
          columns={columns}
          data={rows}
          isLoading={isLoading}
          emptyText="尚無已完成分析"
        />
      </section>
    </div>
  );
}

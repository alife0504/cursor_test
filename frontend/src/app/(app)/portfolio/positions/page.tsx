"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { DataTable } from "@/components/common/DataTable";
import { MarketBadge } from "@/components/common/MarketBadge";
import { NumberFormat } from "@/components/common/NumberFormat";
import { usePositions, type PortfolioPosition } from "@/hooks/usePortfolio";

// Phase 17 § J:模擬持倉
//   - 從已核准訂單聚合(v7.0 不擴大後端)
//   - 顯示 symbol / qty / avg_cost / total_cost
//   - 未來 v1.1 加 portfolio_positions endpoint 後改為直接讀

export default function PortfolioPositionsPage() {
  const { positions, isLoading } = usePositions();

  const summary = useMemo(() => {
    const total = positions.reduce(
      (acc, p) => acc + Math.abs(Number(p.total_cost)),
      0,
    );
    return { count: positions.length, totalCost: total };
  }, [positions]);

  const columns = useMemo<ColumnDef<PortfolioPosition>[]>(
    () => [
      {
        accessorKey: "symbol",
        header: "代號",
        cell: ({ row }) => (
          <Link
            href={`/analysis/new?symbol=${row.original.symbol}`}
            className="font-mono text-primary hover:underline"
          >
            {row.original.symbol}
          </Link>
        ),
      },
      {
        accessorKey: "market",
        header: "市場",
        cell: ({ row }) => <MarketBadge market={row.original.market} />,
      },
      {
        accessorKey: "qty",
        header: "持股(股)",
        cell: ({ row }) => (
          <NumberFormat
            value={row.original.qty}
            className={
              row.original.qty >= 0 ? "text-emerald-600" : "text-rose-600"
            }
          />
        ),
      },
      {
        accessorKey: "avg_cost",
        header: "平均成本",
        cell: ({ row }) => <NumberFormat value={row.original.avg_cost} decimals={2} />,
      },
      {
        accessorKey: "total_cost",
        header: "累計成本",
        cell: ({ row }) => <NumberFormat value={row.original.total_cost} decimals={2} />,
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">模擬持倉</h1>
        <p className="text-sm text-muted-foreground">
          由已核准的訂單聚合計算;v1.1 將支援即時市價與 P&amp;L
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground">持有檔數</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{summary.count}</p>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground">累計投入成本</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">
            <NumberFormat value={summary.totalCost} decimals={0} />
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={positions}
        isLoading={isLoading}
        emptyText="目前無已核准訂單,請至 /portfolio/orders 核准訂單"
      />
    </div>
  );
}

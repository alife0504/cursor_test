"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Briefcase, Wallet } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { DataTable } from "@/components/common/DataTable";
import { KpiCard } from "@/components/common/KpiCard";
import { MarketBadge } from "@/components/common/MarketBadge";
import { NumberFormat } from "@/components/common/NumberFormat";
import { PageHeader } from "@/components/common/PageHeader";
import { usePositions, type PortfolioPosition } from "@/hooks/usePortfolio";

// 模擬持倉：從已核准訂單聚合
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
        header: "持股（股）",
        cell: ({ row }) => (
          <NumberFormat
            value={row.original.qty}
            className={
              row.original.qty >= 0 ? "text-bull" : "text-bear"
            }
          />
        ),
      },
      {
        accessorKey: "avg_cost",
        header: "平均成本",
        cell: ({ row }) => (
          <NumberFormat value={row.original.avg_cost} decimals={2} />
        ),
      },
      {
        accessorKey: "total_cost",
        header: "累計成本",
        cell: ({ row }) => (
          <NumberFormat value={row.original.total_cost} decimals={2} />
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="模擬持倉"
        description="由已核准的訂單聚合計算；v1.1 將支援即時市價與 P&L"
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <KpiCard
          title="持有檔數"
          value={summary.count}
          icon={Briefcase}
          accent="primary"
        />
        <KpiCard
          title="累計投入成本"
          value={<NumberFormat value={summary.totalCost} decimals={0} />}
          icon={Wallet}
          accent="info"
        />
      </div>

      <DataTable
        columns={columns}
        data={positions}
        isLoading={isLoading}
        emptyText="目前無已核准訂單；請至「待核准訂單」核准訂單"
      />
    </div>
  );
}

"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { DataTable } from "@/components/common/DataTable";
import { NumberFormat } from "@/components/common/NumberFormat";
import { PriceDelta } from "@/components/common/PriceDelta";
import { useMarketMovers } from "@/hooks/useMarket";
import type { MoverRow } from "@/lib/api-types";

// Phase 17 § B:漲幅 / 跌幅 / 成交量榜
type MoverType = "gainers" | "losers" | "volume";

interface MoversTableProps {
  type: MoverType;
  market: "TW" | "US";
  limit?: number;
}

export function MoversTable({ type, market, limit = 10 }: MoversTableProps) {
  const { data, isLoading } = useMarketMovers(type, market, limit);

  const columns = useMemo<ColumnDef<MoverRow>[]>(
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
        accessorKey: "name",
        header: "名稱",
        cell: ({ row }) => row.original.name ?? "-",
      },
      {
        accessorKey: "close",
        header: "收盤",
        cell: ({ row }) => (
          <NumberFormat
            value={row.original.close ?? null}
            className="tabular-nums"
          />
        ),
      },
      {
        accessorKey: "change_pct",
        header: "漲跌幅",
        cell: ({ row }) => (
          <PriceDelta
            value={row.original.change_pct ?? null}
            mode="raw"
            showIcon={false}
          />
        ),
      },
      ...(type === "volume"
        ? [
            {
              accessorKey: "volume",
              header: "成交量",
              cell: ({ row }: { row: { original: MoverRow } }) => (
                <NumberFormat value={row.original.volume ?? null} />
              ),
            } as ColumnDef<MoverRow>,
          ]
        : []),
    ],
    [type],
  );

  return (
    <DataTable
      columns={columns}
      data={data ?? []}
      isLoading={isLoading}
      emptyText="尚無資料"
    />
  );
}

"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { NumberFormat } from "@/components/common/NumberFormat";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { PercentFormat } from "@/components/common/PercentFormat";
import {
  loadLastFilters,
  ScreenerForm,
} from "@/components/screener/ScreenerForm";
import { useScreener } from "@/hooks/useScreener";
import type { ScreenerFilters, ScreenerRow } from "@/lib/api-types";

// Phase 17 § E:選股篩選器
//   - 從 localStorage 載入上次條件
//   - submit form → 套用條件 → 結果表
//   - cursor pagination

export default function ScreenerFilterPage() {
  const [filters, setFilters] = useState<ScreenerFilters>({ market: "TW" });
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([]);

  useEffect(() => {
    const last = loadLastFilters();
    if (last) setFilters(last);
  }, []);

  const { data, isLoading } = useScreener({ ...filters, cursor });

  const columns = useMemo<ColumnDef<ScreenerRow>[]>(
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
        accessorKey: "industry",
        header: "產業",
        cell: ({ row }) => row.original.industry ?? "-",
      },
      {
        accessorKey: "close",
        header: "收盤",
        cell: ({ row }) => <NumberFormat value={row.original.close ?? null} decimals={2} />,
      },
      {
        accessorKey: "pe",
        header: "PE",
        cell: ({ row }) => <NumberFormat value={row.original.pe ?? null} decimals={2} />,
      },
      {
        accessorKey: "dividend_yield",
        header: "殖利率",
        cell: ({ row }) => (
          <PercentFormat value={row.original.dividend_yield ?? null} colored />
        ),
      },
      {
        accessorKey: "eps_growth",
        header: "EPS 成長",
        cell: ({ row }) => (
          <PercentFormat value={row.original.eps_growth ?? null} colored />
        ),
      },
      {
        accessorKey: "rsi",
        header: "RSI",
        cell: ({ row }) => <NumberFormat value={row.original.rsi ?? null} decimals={1} />,
      },
    ],
    [],
  );

  const handleSubmit = (f: ScreenerFilters) => {
    setFilters(f);
    setCursor(null);
    setCursorStack([]);
  };

  const handleNext = () => {
    if (!data?.nextCursor) return;
    setCursorStack((s) => [...s, cursor]);
    setCursor(data.nextCursor);
  };

  const handlePrev = () => {
    const prev = cursorStack[cursorStack.length - 1] ?? null;
    setCursorStack((s) => s.slice(0, -1));
    setCursor(prev);
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="選股篩選器"
        description="PE / 殖利率 / EPS 成長 / RSI / 市值多條件複合篩選"
      />

      <ScreenerForm initial={filters} onSubmit={handleSubmit} />

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        isLoading={isLoading}
        emptyText="尚無符合條件的股票,請調整篩選條件"
      />

      <Pagination
        hasMore={data?.hasMore ?? false}
        onNext={handleNext}
        onPrev={handlePrev}
        canGoBack={cursorStack.length > 0}
      />
    </div>
  );
}

"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { NumberFormat } from "@/components/common/NumberFormat";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useInstitutional } from "@/hooks/useNews";
import type { InstitutionalRow } from "@/lib/api-types";

// Phase 17 § C:三大法人(TW only)

export default function InstitutionalPage() {
  const [date, setDate] = useState<string>("");
  const { data, isLoading } = useInstitutional({
    market: "TW",
    date: date || null,
    limit: 50,
  });

  const rows = useMemo(() => data?.rows ?? [], [data?.rows]);
  const usedDate = data?.date ?? null;

  // 個股買超 top 10:依 foreign_net desc
  const topBuyers = useMemo(() => {
    return [...rows]
      .sort((a, b) => Number(b.foreign_net ?? 0) - Number(a.foreign_net ?? 0))
      .slice(0, 10);
  }, [rows]);

  const columns = useMemo<ColumnDef<InstitutionalRow>[]>(
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
        accessorKey: "foreign_net",
        header: "外資買賣超",
        cell: ({ row }) => (
          <NumberFormat
            value={row.original.foreign_net ?? null}
            className={
              Number(row.original.foreign_net ?? 0) >= 0
                ? "text-emerald-600"
                : "text-rose-600"
            }
          />
        ),
      },
      {
        accessorKey: "trust_net",
        header: "投信買賣超",
        cell: ({ row }) => (
          <NumberFormat
            value={row.original.trust_net ?? null}
            className={
              Number(row.original.trust_net ?? 0) >= 0
                ? "text-emerald-600"
                : "text-rose-600"
            }
          />
        ),
      },
      {
        accessorKey: "dealer_net",
        header: "自營商買賣超",
        cell: ({ row }) => (
          <NumberFormat
            value={row.original.dealer_net ?? null}
            className={
              Number(row.original.dealer_net ?? 0) >= 0
                ? "text-emerald-600"
                : "text-rose-600"
            }
          />
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">三大法人</h1>
          <p className="text-sm text-muted-foreground">
            外資、投信、自營商買賣超(台股){usedDate ? ` · ${usedDate}` : ""}
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor="inst-date" className="text-xs">
              日期(留空為最新)
            </Label>
            <Input
              id="inst-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-44"
            />
          </div>
        </div>
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">外資買超 Top 10</h3>
        <DataTable
          columns={columns}
          data={topBuyers}
          isLoading={isLoading}
          emptyText="該日期無三大法人資料"
        />
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">全部個股(本日)</h3>
        <DataTable
          columns={columns}
          data={rows}
          isLoading={isLoading}
          emptyText="該日期無三大法人資料"
        />
      </section>
    </div>
  );
}

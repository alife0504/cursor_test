"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Briefcase, Building2, Globe, Layers, PieChart } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { KpiCard } from "@/components/common/KpiCard";
import { NumberFormat } from "@/components/common/NumberFormat";
import { PageHeader } from "@/components/common/PageHeader";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useInstitutional } from "@/hooks/useNews";
import type { InstitutionalRow } from "@/lib/api-types";

// Phase 17 § C:三大法人(TW only)

// 大數字精簡顯示（億 / 萬）；紅買超綠賣超由 accent 表達
function compactNet(n: number): string {
  const abs = Math.abs(n);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)} 億`;
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(1)} 萬`;
  return `${sign}${abs.toLocaleString()}`;
}

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

  // 三大法人淨額合計（本日，用已載入資料彙總）
  const totals = useMemo(() => {
    const f = rows.reduce((a, r) => a + Number(r.foreign_net ?? 0), 0);
    const t = rows.reduce((a, r) => a + Number(r.trust_net ?? 0), 0);
    const d = rows.reduce((a, r) => a + Number(r.dealer_net ?? 0), 0);
    return { f, t, d, count: rows.length };
  }, [rows]);
  const netAccent = (n: number): "bull" | "bear" | undefined =>
    n > 0 ? "bull" : n < 0 ? "bear" : undefined;

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
                ? "text-bull"
                : "text-bear"
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
                ? "text-bull"
                : "text-bear"
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
                ? "text-bull"
                : "text-bear"
            }
          />
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={PieChart}
        title="三大法人"
        description={
          <>
            外資、投信、自營商買賣超（台股）
            {usedDate ? ` · ${usedDate}` : ""}
          </>
        }
        actions={
          <div className="flex flex-col gap-1">
            <Label htmlFor="inst-date" className="text-xs">
              日期（留空為最新）
            </Label>
            <Input
              id="inst-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-44"
            />
          </div>
        }
      />

      {/* 三大法人淨額合計 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="外資淨額合計"
          value={compactNet(totals.f)}
          subtitle="紅買超 · 綠賣超"
          icon={Globe}
          accent={netAccent(totals.f)}
        />
        <KpiCard
          title="投信淨額合計"
          value={compactNet(totals.t)}
          subtitle="紅買超 · 綠賣超"
          icon={Building2}
          accent={netAccent(totals.t)}
        />
        <KpiCard
          title="自營商淨額合計"
          value={compactNet(totals.d)}
          subtitle="紅買超 · 綠賣超"
          icon={Briefcase}
          accent={netAccent(totals.d)}
        />
        <KpiCard
          title="本日個股數"
          value={totals.count}
          subtitle="有三大法人資料"
          icon={Layers}
          accent="primary"
        />
      </section>

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

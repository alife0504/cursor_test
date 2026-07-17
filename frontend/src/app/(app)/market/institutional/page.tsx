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
  const common = { market: "TW" as const, date: date || null, limit: 10 };
  // 6 個榜：外資 / 投信 / 自營商，各買超（desc）與賣超（asc）。totals 取自第一個查詢。
  const foreignBuy = useInstitutional({ ...common, by: "foreign", order: "buy" });
  const foreignSell = useInstitutional({ ...common, by: "foreign", order: "sell" });
  const trustBuy = useInstitutional({ ...common, by: "trust", order: "buy" });
  const trustSell = useInstitutional({ ...common, by: "trust", order: "sell" });
  const dealerBuy = useInstitutional({ ...common, by: "dealer", order: "buy" });
  const dealerSell = useInstitutional({ ...common, by: "dealer", order: "sell" });

  const usedDate = foreignBuy.data?.date ?? null;

  // 三大法人淨額合計（本日，全市場）——用後端 SUM 全母體的 totals，
  // 不可拿榜單（截斷的 Top 10）加總，否則方向會與市場相反。
  const totals = useMemo(() => {
    const tt = foreignBuy.data?.totals;
    return {
      f: Number(tt?.foreign_net ?? 0),
      t: Number(tt?.trust_net ?? 0),
      d: Number(tt?.dealer_net ?? 0),
      count: Number(tt?.count ?? 0),
    };
  }, [foreignBuy.data?.totals]);
  const netAccent = (n: number): "bull" | "bear" | undefined =>
    n > 0 ? "bull" : n < 0 ? "bear" : undefined;

  const sections = [
    { title: "外資買超 Top 10", q: foreignBuy },
    { title: "外資賣超 Top 10", q: foreignSell },
    { title: "投信買超 Top 10", q: trustBuy },
    { title: "投信賣超 Top 10", q: trustSell },
    { title: "自營商買超 Top 10", q: dealerBuy },
    { title: "自營商賣超 Top 10", q: dealerSell },
  ];

  const columns = useMemo<ColumnDef<InstitutionalRow>[]>(
    () => [
      {
        accessorKey: "symbol",
        header: "代號",
        meta: { align: "left" },
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
        meta: { align: "left" },
        cell: ({ row }) => (
          <span className="whitespace-nowrap">{row.original.name ?? "-"}</span>
        ),
      },
      {
        accessorKey: "foreign_net",
        header: "外資買賣超",
        meta: { align: "right" },
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
        meta: { align: "right" },
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
        meta: { align: "right" },
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

      {sections.map((s) => (
        <section key={s.title} className="space-y-2">
          <h3 className="text-sm font-medium">{s.title}</h3>
          <DataTable
            columns={columns}
            data={s.q.data?.rows ?? []}
            isLoading={s.q.isLoading}
            emptyText="該日期無三大法人資料"
          />
        </section>
      ))}
    </div>
  );
}

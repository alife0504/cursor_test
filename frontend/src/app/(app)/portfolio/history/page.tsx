"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { CheckCircle2, History, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { KpiCard } from "@/components/common/KpiCard";
import { MarketBadge } from "@/components/common/MarketBadge";
import { NumberFormat } from "@/components/common/NumberFormat";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SignalBadge } from "@/components/common/SignalBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTradeHistory } from "@/hooks/usePortfolio";
import type { OrderSummary } from "@/lib/api-types";

// Phase 17 § K:交易記錄
//   - 從 orders 全部紀錄聚合(篩 symbol / side / date range)
//   - 點 analysis_id 跳分析詳情

export default function TradeHistoryPage() {
  const [symbol, setSymbol] = useState<string>("");
  const [side, setSide] = useState<"BUY" | "SELL" | "all">("all");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([]);

  const { items, data, isLoading } = useTradeHistory({
    symbol: symbol || null,
    side: side === "all" ? null : side,
    cursor,
  });

  const summary = useMemo(() => {
    const buy = items.filter((o) => o.side === "BUY").length;
    const sell = items.filter((o) => o.side === "SELL").length;
    const approved = items.filter((o) => o.status === "APPROVED").length;
    return { n: items.length, buy, sell, approved };
  }, [items]);

  const columns = useMemo<ColumnDef<OrderSummary>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "建立時間",
        cell: ({ row }) => (
          <span className="tabular-nums text-xs">
            {row.original.created_at?.slice(0, 16) ?? "-"}
          </span>
        ),
      },
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
        accessorKey: "side",
        header: "方向",
        cell: ({ row }) => (
          <SignalBadge signal={row.original.side} status="completed" />
        ),
      },
      {
        accessorKey: "qty",
        header: "股數",
        cell: ({ row }) => <NumberFormat value={row.original.qty} />,
      },
      {
        accessorKey: "target_price",
        header: "目標價",
        cell: ({ row }) => (
          <NumberFormat value={row.original.target_price ?? null} decimals={2} />
        ),
      },
      {
        accessorKey: "status",
        header: "狀態",
        cell: ({ row }) => (
          <span className="text-xs font-medium">{row.original.status}</span>
        ),
      },
      {
        id: "analysis",
        header: "分析",
        cell: ({ row }) =>
          row.original.analysis_id ? (
            <Link
              href={`/analysis/${row.original.analysis_id}`}
              className="text-xs text-primary hover:underline"
            >
              查看
            </Link>
          ) : (
            <span className="text-xs text-muted-foreground">-</span>
          ),
      },
    ],
    [],
  );

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
        icon={History}
        title="交易記錄"
        description="全部訂單（含 APPROVED / REJECTED / PENDING 等）；可篩選 symbol 與方向"
      />

      {/* 摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="本頁筆數"
          value={summary.n}
          subtitle={`已核准 ${summary.approved} 筆`}
          icon={History}
          accent="primary"
        />
        <KpiCard
          title="買入 BUY"
          value={summary.buy}
          subtitle="紅漲 · 做多"
          icon={TrendingUp}
          accent="bull"
        />
        <KpiCard
          title="賣出 SELL"
          value={summary.sell}
          subtitle="綠跌 · 做空"
          icon={TrendingDown}
          accent="bear"
        />
        <KpiCard
          title="已核准"
          value={summary.approved}
          subtitle="實際成交訂單"
          icon={CheckCircle2}
          accent="info"
        />
      </section>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="hist-symbol" className="text-xs">代號</Label>
          <Input
            id="hist-symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="例:2330"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="hist-side" className="text-xs">方向</Label>
          <Select value={side} onValueChange={(v) => setSide(v as typeof side)}>
            <SelectTrigger id="hist-side">
              <SelectValue placeholder="全部" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="BUY">買入</SelectItem>
              <SelectItem value="SELL">賣出</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={items}
        isLoading={isLoading}
        emptyText="無交易記錄"
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

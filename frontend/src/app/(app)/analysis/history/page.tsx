"use client";

import { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { Activity, ArrowRight, Coins, History, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { ErrorState } from "@/components/common/ErrorState";
import { KpiCard } from "@/components/common/KpiCard";
import { MarketBadge } from "@/components/common/MarketBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SignalBadge } from "@/components/common/SignalBadge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAnalysisList } from "@/hooks/useAnalysis";
import type { AnalysisSummary } from "@/lib/api-types";

// Phase 16 § F:分析歷史
export default function HistoryPage() {
  const [symbol, setSymbol] = useState("");
  const [status, setStatus] = useState<string>("ALL");
  const [applied, setApplied] = useState<{ symbol?: string; status?: string }>({});
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack[cursorStack.length - 1];

  const { data, isLoading, error } = useAnalysisList({
    symbol: applied.symbol || null,
    status: applied.status && applied.status !== "ALL" ? applied.status : null,
    cursor,
  });
  const items = data?.items ?? [];

  // 本頁摘要（用已載入資料即時彙總）
  const summary = useMemo(() => {
    const completed = items.filter((i) => i.status === "completed").length;
    const buy = items.filter((i) => i.signal === "BUY").length;
    const sell = items.filter((i) => i.signal === "SELL").length;
    const cost = items.reduce((a, i) => a + Number(i.total_cost_usd ?? 0), 0);
    return { n: items.length, completed, buy, sell, cost };
  }, [items]);

  const apply = () => {
    setApplied({ symbol, status });
    setCursorStack([null]);
  };
  const clear = () => {
    setSymbol("");
    setStatus("ALL");
    setApplied({});
    setCursorStack([null]);
  };

  const columns: ColumnDef<AnalysisSummary>[] = [
    {
      accessorKey: "symbol",
      header: "代號",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span className="font-medium">{row.original.symbol}</span>
          <MarketBadge market={row.original.market} />
        </div>
      ),
    },
    {
      accessorKey: "status",
      header: "狀態 / 訊號",
      cell: ({ row }) => (
        <SignalBadge
          signal={row.original.signal}
          status={row.original.status}
        />
      ),
    },
    {
      accessorKey: "confidence",
      header: "信心",
      cell: ({ row }) => (
        <span className="tabular-nums">{row.original.confidence ?? "-"}</span>
      ),
    },
    {
      accessorKey: "llm_model",
      header: "模型",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {row.original.llm_model ?? "-"}
        </span>
      ),
    },
    {
      accessorKey: "total_cost_usd",
      header: "Cost",
      cell: ({ row }) => (
        <span className="tabular-nums">
          {row.original.total_cost_usd ?? "-"}
        </span>
      ),
    },
    {
      accessorKey: "created_at",
      header: "建立時間",
      cell: ({ row }) => (
        <DateFormat value={row.original.created_at} mode="datetime" />
      ),
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <Link
          href={`/analysis/${row.original.id}`}
          className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
        >
          查看 <ArrowRight className="ml-1 h-3 w-3" />
        </Link>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={History}
        title="分析歷史"
        description="檢視過往分析、訊號與費用"
      />

      {/* 摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="本頁分析"
          value={summary.n}
          subtitle={`已完成 ${summary.completed} 筆`}
          icon={Activity}
          accent="primary"
        />
        <KpiCard
          title="看多訊號 BUY"
          value={summary.buy}
          subtitle="紅漲 · 看多建議"
          icon={TrendingUp}
          accent="bull"
        />
        <KpiCard
          title="看空訊號 SELL"
          value={summary.sell}
          subtitle="綠跌 · 看空建議"
          icon={TrendingDown}
          accent="bear"
        />
        <KpiCard
          title="本頁總成本"
          value={`US$${summary.cost.toFixed(3)}`}
          subtitle="LLM 推論費用"
          icon={Coins}
          accent="info"
        />
      </section>

      <div className="grid grid-cols-1 gap-2 rounded-md border p-3 md:grid-cols-4">
        <div className="space-y-1.5">
          <Label htmlFor="h-symbol">代號</Label>
          <Input
            id="h-symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="2330 / AAPL"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="h-status">狀態</Label>
          <Select
            value={status}
            onValueChange={(v) => setStatus(v ?? "ALL")}
          >
            <SelectTrigger id="h-status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">全部</SelectItem>
              <SelectItem value="queued">排隊中</SelectItem>
              <SelectItem value="running">分析中</SelectItem>
              <SelectItem value="completed">已完成</SelectItem>
              <SelectItem value="failed">失敗</SelectItem>
              <SelectItem value="cancelled">已取消</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="md:col-span-2 flex items-end justify-end gap-2">
          <Button variant="outline" onClick={clear}>
            清除
          </Button>
          <Button onClick={apply}>套用</Button>
        </div>
      </div>

      {error ? (
        <ErrorState
          title="無法載入分析列表"
          variant="inline"
          onRetry={() => {
            if (typeof window !== "undefined") window.location.reload();
          }}
          error={error}
        />
      ) : null}

      <DataTable
        columns={columns}
        data={items}
        isLoading={isLoading}
        emptyText="目前條件下沒有分析紀錄"
      />

      <Pagination
        hasMore={!!data?.hasMore}
        canGoBack={cursorStack.length > 1}
        onPrev={() => setCursorStack((s) => s.slice(0, -1))}
        onNext={() =>
          data?.nextCursor &&
          setCursorStack((s) => [...s, data.nextCursor as string])
        }
      />
    </div>
  );
}

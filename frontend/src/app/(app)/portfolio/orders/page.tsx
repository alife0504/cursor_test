"use client";

import { ColumnDef } from "@tanstack/react-table";
import {
  Check,
  Clock,
  ExternalLink,
  ListChecks,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { ErrorState } from "@/components/common/ErrorState";
import { KpiCard } from "@/components/common/KpiCard";
import { MarketBadge } from "@/components/common/MarketBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { OrderApprovalDialog } from "@/components/orders/OrderApprovalDialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useOrders } from "@/hooks/useOrders";
import type { OrderSummary } from "@/lib/api-types";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<string, string> = {
  PENDING: "待核准",
  APPROVED: "已核准",
  REJECTED: "已拒絕",
  EXPIRED: "已過期",
  CANCELLED: "已取消",
};

const STATUS_STYLE: Record<string, string> = {
  PENDING: "bg-warning/10 text-warning ring-1 ring-warning/20",
  APPROVED: "bg-success/10 text-success ring-1 ring-success/20",
  REJECTED: "bg-destructive/10 text-destructive ring-1 ring-destructive/20",
  EXPIRED: "bg-muted text-muted-foreground ring-1 ring-border",
  CANCELLED: "bg-muted text-muted-foreground ring-1 ring-border line-through",
};

// 訂單核准頁
export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<string>("PENDING");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack[cursorStack.length - 1];
  const [target, setTarget] = useState<{
    order: OrderSummary;
    mode: "approve" | "reject";
  } | null>(null);

  const { data, isLoading, error, refetch } = useOrders({
    status: statusFilter && statusFilter !== "ALL" ? statusFilter : null,
    cursor,
  });
  const items = data?.items ?? [];

  const summary = useMemo(() => {
    const buy = items.filter((o) => o.side === "BUY").length;
    const sell = items.filter((o) => o.side === "SELL").length;
    const pending = items.filter((o) => o.status === "PENDING").length;
    return { n: items.length, buy, sell, pending };
  }, [items]);

  const columns: ColumnDef<OrderSummary>[] = [
    {
      accessorKey: "symbol",
      header: "代號",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span className="font-mono font-medium">{row.original.symbol}</span>
          <MarketBadge market={row.original.market} />
        </div>
      ),
    },
    {
      accessorKey: "side",
      header: "方向",
      cell: ({ row }) => (
        <Badge
          variant="secondary"
          data-side={row.original.side}
          className={cn(
            "font-semibold",
            row.original.side === "BUY"
              ? "bg-signal-buy-muted text-signal-buy ring-1 ring-signal-buy/20"
              : "bg-signal-sell-muted text-signal-sell ring-1 ring-signal-sell/20",
          )}
        >
          {row.original.side === "BUY" ? "買進" : "賣出"}
        </Badge>
      ),
    },
    {
      accessorKey: "qty",
      header: "數量",
      cell: ({ row }) => <span className="num">{row.original.qty}</span>,
    },
    {
      accessorKey: "target_price",
      header: "目標價",
      cell: ({ row }) => (
        <span className="num">{row.original.target_price ?? "—"}</span>
      ),
    },
    {
      accessorKey: "status",
      header: "狀態",
      cell: ({ row }) => (
        <Badge
          variant="secondary"
          className={cn(
            "uppercase",
            STATUS_STYLE[row.original.status] ?? "bg-muted text-muted-foreground",
          )}
        >
          {STATUS_LABEL[row.original.status] ?? row.original.status}
        </Badge>
      ),
    },
    {
      accessorKey: "analysis_id",
      header: "Analysis",
      cell: ({ row }) =>
        row.original.analysis_id ? (
          <Link
            href={`/analysis/${row.original.analysis_id}`}
            className={cn(
              buttonVariants({ variant: "link", size: "sm" }),
              "h-auto p-0",
            )}
          >
            查看 <ExternalLink className="ml-1 h-3 w-3" />
          </Link>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
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
      header: () => <span className="sr-only">操作</span>,
      cell: ({ row }) => {
        const isPending = row.original.status === "PENDING";
        if (!isPending) {
          return <span className="text-xs text-muted-foreground">—</span>;
        }
        return (
          <div className="flex items-center justify-end gap-1">
            <Button
              size="sm"
              onClick={() =>
                setTarget({ order: row.original, mode: "approve" })
              }
              className="gap-1"
            >
              <Check className="h-3 w-3" /> 核准
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() =>
                setTarget({ order: row.original, mode: "reject" })
              }
              className="gap-1"
            >
              <X className="h-3 w-3" /> 拒絕
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={ListChecks}
        title="待核准訂單"
        description="分析完成後若 signal=BUY/SELL 自動產生 PENDING 訂單。雙重確認核准。"
        actions={
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">狀態</span>
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v ?? "ALL")}
            >
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部</SelectItem>
                <SelectItem value="PENDING">PENDING</SelectItem>
                <SelectItem value="APPROVED">APPROVED</SelectItem>
                <SelectItem value="REJECTED">REJECTED</SelectItem>
                <SelectItem value="EXPIRED">EXPIRED</SelectItem>
              </SelectContent>
            </Select>
          </div>
        }
      />

      {/* 摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="本頁訂單"
          value={summary.n}
          subtitle={`待核准 ${summary.pending} 筆`}
          icon={ListChecks}
          accent="primary"
        />
        <KpiCard
          title="買進 BUY"
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
          title="待核准"
          value={summary.pending}
          subtitle="需人工雙重確認"
          icon={Clock}
          accent="warning"
        />
      </section>

      {error ? (
        <ErrorState
          title="無法載入訂單列表"
          variant="inline"
          onRetry={refetch}
          error={error}
        />
      ) : null}

      <DataTable
        columns={columns}
        data={items}
        isLoading={isLoading}
        emptyText="此狀態下沒有訂單"
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

      <OrderApprovalDialog
        order={target?.order ?? null}
        mode={target?.mode ?? null}
        onClose={() => setTarget(null)}
      />
    </div>
  );
}

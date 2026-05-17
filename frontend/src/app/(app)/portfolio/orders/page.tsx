"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Check, ExternalLink, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { MarketBadge } from "@/components/common/MarketBadge";
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

// Phase 16 § H:訂單核准頁
export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<string>("PENDING");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack[cursorStack.length - 1];
  const [target, setTarget] = useState<{
    order: OrderSummary;
    mode: "approve" | "reject";
  } | null>(null);

  const { data, isLoading, error } = useOrders({
    status: statusFilter && statusFilter !== "ALL" ? statusFilter : null,
    cursor,
  });
  const items = data?.items ?? [];

  const columns: ColumnDef<OrderSummary>[] = [
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
      accessorKey: "side",
      header: "方向",
      cell: ({ row }) => (
        <Badge
          variant="secondary"
          className={cn(
            row.original.side === "BUY"
              ? "bg-emerald-100 text-emerald-900"
              : "bg-rose-100 text-rose-900",
          )}
        >
          {row.original.side}
        </Badge>
      ),
    },
    {
      accessorKey: "qty",
      header: "數量",
      cell: ({ row }) => (
        <span className="tabular-nums">{row.original.qty}</span>
      ),
    },
    {
      accessorKey: "target_price",
      header: "目標價",
      cell: ({ row }) => (
        <span className="tabular-nums">
          {row.original.target_price ?? "-"}
        </span>
      ),
    },
    {
      accessorKey: "status",
      header: "狀態",
      cell: ({ row }) => (
        <Badge variant="outline">{row.original.status}</Badge>
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
          <span className="text-xs text-muted-foreground">-</span>
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
          return (
            <span className="text-xs text-muted-foreground">已處理</span>
          );
        }
        return (
          <div className="flex items-center gap-1">
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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">待核准訂單</h1>
        <p className="text-sm text-muted-foreground">
          分析完成後若 signal=BUY/SELL 自動產生 PENDING 訂單;雙重確認核准
        </p>
      </div>

      <div className="flex items-center justify-end gap-2">
        <span className="text-sm text-muted-foreground">狀態:</span>
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v ?? "ALL")}
        >
          <SelectTrigger className="w-40">
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

      {error ? (
        <p className="text-sm text-destructive">無法載入訂單列表</p>
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

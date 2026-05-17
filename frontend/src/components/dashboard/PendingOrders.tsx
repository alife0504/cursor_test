"use client";

import Link from "next/link";

import { DateFormat } from "@/components/common/DateFormat";
import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { useOrders } from "@/hooks/useOrders";
import { cn } from "@/lib/utils";

// Phase 16 § B:儀表板 — 待核准訂單(最近 5 筆 PENDING)
export function PendingOrders({ limit = 5 }: { limit?: number }) {
  const { data, isLoading, error } = useOrders({ status: "PENDING", limit });
  const items = data?.items ?? [];

  if (isLoading) return <LoadingSkeleton rows={3} />;
  if (error) return <p className="text-sm text-destructive">無法載入訂單</p>;
  if (!items.length) {
    return (
      <EmptyState
        title="目前沒有待核准訂單"
        description="分析完成後若產生 BUY/SELL 訊號會自動建立 PENDING 訂單"
      />
    );
  }
  return (
    <div className="flex flex-col divide-y">
      {items.map((it) => (
        <div
          key={it.id}
          className="flex items-center justify-between py-2 px-2 -mx-2 rounded-md hover:bg-muted/40"
        >
          <div className="flex items-center gap-2">
            <Badge
              variant="secondary"
              className={cn(
                it.side === "BUY"
                  ? "bg-emerald-100 text-emerald-900"
                  : "bg-rose-100 text-rose-900",
              )}
            >
              {it.side}
            </Badge>
            <span className="font-medium">{it.symbol}</span>
            <span className="text-xs text-muted-foreground">
              x{it.qty}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            <DateFormat value={it.created_at} mode="relative" />
          </div>
        </div>
      ))}
      <div className="pt-2">
        <Link
          href="/portfolio/orders"
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "w-full",
          )}
        >
          前往核准
        </Link>
      </div>
    </div>
  );
}

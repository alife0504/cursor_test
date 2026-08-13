"use client";

import Link from "next/link";

import { DateFormat } from "@/components/common/DateFormat";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { useOrders } from "@/hooks/useOrders";
import { cn } from "@/lib/utils";

// 待核准訂單 widget — 用紅綠 token + 統一 ErrorState/EmptyState
export function PendingOrders({ limit = 5 }: { limit?: number }) {
  const { data, isLoading, error, refetch } = useOrders({
    status: "PENDING",
    limit,
  });
  const items = data?.items ?? [];

  if (isLoading) return <LoadingSkeleton rows={3} />;
  if (error) {
    return (
      <ErrorState
        title="無法載入訂單"
        variant="inline"
        onRetry={refetch}
        error={error}
      />
    );
  }
  if (!items.length) {
    return (
      <EmptyState
        title="目前沒有待核准訂單"
        description="分析完成後若產生 BUY/SELL 訊號會自動建立 PENDING 訂單"
        variant="inline"
      />
    );
  }
  return (
    <div className="flex flex-col divide-y">
      {items.map((it) => (
        <Link
          key={it.id}
          href="/portfolio/orders"
          className="flex items-center justify-between -mx-2 rounded-md px-2 py-2 transition-colors hover:bg-muted/40"
        >
          <div className="flex items-center gap-2">
            <Badge
              variant="secondary"
              data-side={it.side}
              className={cn(
                "font-semibold",
                it.side === "BUY"
                  ? "bg-signal-buy-muted text-signal-buy ring-1 ring-signal-buy/20"
                  : "bg-signal-sell-muted text-signal-sell ring-1 ring-signal-sell/20",
              )}
            >
              {it.side === "BUY" ? "買進" : "賣出"}
            </Badge>
            <span className="font-mono font-medium">{it.symbol}</span>
            <span className="num text-xs text-muted-foreground">
              × {it.qty}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            <DateFormat value={it.created_at} mode="relative" />
          </div>
        </Link>
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

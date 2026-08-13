"use client";

import { ArrowRight, Star } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { MarketBadge } from "@/components/common/MarketBadge";
import { Card, CardContent } from "@/components/ui/card";
import { useWatchlist } from "@/hooks/useWatchlist";

/**
 * 儀表板 — 自選股 mini cards（v1.0 不顯即時報價）
 * 點 symbol → 直接 /analysis/new?symbol=...
 */
export function WatchlistMiniCards({ limit = 6 }: { limit?: number }) {
  const { data, isLoading, error, refetch } = useWatchlist();
  const items = (data ?? []).slice(0, limit);

  if (isLoading) return <LoadingSkeleton rows={2} />;
  if (error) {
    return (
      <ErrorState
        title="無法載入自選股"
        variant="inline"
        onRetry={refetch}
        error={error}
      />
    );
  }
  if (!items.length) {
    return (
      <EmptyState
        icon={Star}
        title="尚未加入任何自選股"
        description="到「自選股清單」頁面新增"
        variant="inline"
        action={{
          label: "前往",
          onClick: () => {
            if (typeof window !== "undefined")
              window.location.href = "/screener/watchlist";
          },
        }}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((it) => (
        <Card key={it.id} className="card-hover">
          <CardContent className="flex items-center justify-between p-3.5">
            <div className="flex min-w-0 flex-col">
              <Link
                href={`/analysis/new?symbol=${encodeURIComponent(it.symbol)}`}
                className="inline-flex items-center gap-1 font-mono text-sm font-semibold hover:text-primary hover:underline"
              >
                {it.symbol}
                <ArrowRight className="h-3 w-3 opacity-50" />
              </Link>
              <span className="line-clamp-1 text-xs text-muted-foreground">
                {it.notes || it.tag || "—"}
              </span>
            </div>
            <MarketBadge market={it.market} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

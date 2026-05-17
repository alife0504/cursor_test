"use client";

import Link from "next/link";

import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { MarketBadge } from "@/components/common/MarketBadge";
import { Card, CardContent } from "@/components/ui/card";
import { useWatchlist } from "@/hooks/useWatchlist";

// Phase 16 § B:儀表板 — 自選股 mini cards
// v1.0 只顯示 symbol / name / market;即時價需要 P17 加 /quote 端點(目前先留空)。
export function WatchlistMiniCards({ limit = 6 }: { limit?: number }) {
  const { data, isLoading, error } = useWatchlist();
  const items = (data ?? []).slice(0, limit);

  if (isLoading) return <LoadingSkeleton rows={2} />;
  if (error)
    return (
      <p className="text-sm text-destructive">無法載入自選股,請稍後再試。</p>
    );

  if (!items.length) {
    return (
      <EmptyState
        title="尚未加入任何自選股"
        description="到「自選股清單」頁面新增"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((it) => (
        <Card key={it.id} className="hover:bg-muted/40 transition-colors">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex flex-col">
              <Link
                href={`/analysis/new?symbol=${encodeURIComponent(it.symbol)}`}
                className="font-semibold hover:underline"
              >
                {it.symbol}
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

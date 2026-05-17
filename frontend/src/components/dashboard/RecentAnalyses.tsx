"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { DateFormat } from "@/components/common/DateFormat";
import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { SignalBadge } from "@/components/common/SignalBadge";
import { buttonVariants } from "@/components/ui/button";
import { useAnalysisList } from "@/hooks/useAnalysis";
import { cn } from "@/lib/utils";

// Phase 16 § B:儀表板 — 最近 5 筆分析
export function RecentAnalyses({ limit = 5 }: { limit?: number }) {
  const { data, isLoading, error } = useAnalysisList({ limit });
  const items = data?.items ?? [];

  if (isLoading) return <LoadingSkeleton rows={3} />;
  if (error)
    return (
      <p className="text-sm text-destructive">無法載入分析,請稍後再試。</p>
    );
  if (!items.length) {
    return (
      <EmptyState
        title="尚無分析記錄"
        description="到「新增分析」開始第一筆"
      />
    );
  }

  return (
    <div className="flex flex-col divide-y">
      {items.map((it) => (
        <Link
          key={it.id}
          href={`/analysis/${it.id}`}
          className="flex items-center justify-between py-2 hover:bg-muted/40 transition-colors px-2 -mx-2 rounded-md"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">{it.symbol}</span>
            <span className="text-xs text-muted-foreground">{it.market}</span>
            <SignalBadge signal={it.signal} status={it.status} />
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <DateFormat value={it.created_at} mode="datetime" />
            <ArrowRight className="h-3 w-3" />
          </div>
        </Link>
      ))}
      <div className="pt-2">
        <Link
          href="/analysis/history"
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "w-full",
          )}
        >
          查看所有分析
        </Link>
      </div>
    </div>
  );
}

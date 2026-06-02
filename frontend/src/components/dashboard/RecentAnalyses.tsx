"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { DateFormat } from "@/components/common/DateFormat";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { SignalBadge } from "@/components/common/SignalBadge";
import { buttonVariants } from "@/components/ui/button";
import { useAnalysisList } from "@/hooks/useAnalysis";
import { cn } from "@/lib/utils";

export function RecentAnalyses({ limit = 5 }: { limit?: number }) {
  const { data, isLoading, error, refetch } = useAnalysisList({ limit });
  const items = data?.items ?? [];

  if (isLoading) return <LoadingSkeleton rows={3} />;
  if (error) {
    return (
      <ErrorState
        title="無法載入分析"
        variant="inline"
        onRetry={refetch}
        error={error}
      />
    );
  }
  if (!items.length) {
    return (
      <EmptyState
        title="尚無分析記錄"
        description="到「新增分析」開始第一筆"
        variant="inline"
        action={{
          label: "前往新增",
          onClick: () => {
            if (typeof window !== "undefined")
              window.location.href = "/analysis/new";
          },
        }}
      />
    );
  }

  return (
    <div className="flex flex-col divide-y">
      {items.map((it) => (
        <Link
          key={it.id}
          href={`/analysis/${it.id}`}
          className="-mx-2 flex items-center justify-between rounded-md px-2 py-2 transition-colors hover:bg-muted/40"
        >
          <div className="flex items-center gap-2">
            <span className="font-mono font-medium">{it.symbol}</span>
            <span className="text-[10px] uppercase text-muted-foreground">
              {it.market}
            </span>
            <SignalBadge signal={it.signal} status={it.status} />
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <DateFormat value={it.created_at} mode="relative" />
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

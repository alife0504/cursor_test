import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
}

export function LoadingSkeleton({ rows = 6, className }: LoadingSkeletonProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="overflow-hidden rounded-md border">
      <Skeleton className="h-10 w-full" />
      <div className="flex flex-col gap-2 p-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-full" />
        ))}
      </div>
    </div>
  );
}

/**
 * 模擬 KpiCard 高度的 skeleton（dashboard 用）。
 */
export function KpiSkeleton({ count = 1 }: { count?: number }) {
  return (
    <div
      className={cn(
        "grid gap-3",
        count === 4 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
        count === 3 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        count === 2 && "grid-cols-1 sm:grid-cols-2",
      )}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="overflow-hidden rounded-lg border bg-card p-4"
        >
          <Skeleton className="mb-3 h-3 w-20" />
          <Skeleton className="mb-2 h-8 w-32" />
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-6 w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Card 大區塊 skeleton（dashboard widget / chart container 用）。
 */
export function CardSkeleton({
  height = 200,
  className,
}: {
  height?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border bg-card p-4",
        className,
      )}
    >
      <Skeleton className="mb-3 h-4 w-32" />
      <Skeleton className="w-full" style={{ height }} />
    </div>
  );
}

/**
 * Chart 區塊 skeleton。
 */
export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div
      className="flex w-full items-end justify-around overflow-hidden rounded-md border bg-card p-3"
      style={{ height }}
    >
      {Array.from({ length: 12 }).map((_, i) => (
        <Skeleton
          key={i}
          className="w-3 rounded-t"
          style={{ height: `${30 + ((i * 13) % 70)}%` }}
        />
      ))}
    </div>
  );
}

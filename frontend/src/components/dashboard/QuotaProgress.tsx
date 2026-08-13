"use client";

import BigNumber from "bignumber.js";

import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { Progress } from "@/components/ui/progress";
import { useMyQuota } from "@/hooks/useQuota";
import { cn } from "@/lib/utils";

/**
 * LLM 月用量 progress bar — 用 token 色彩（warning/destructive/success）。
 * 80% 警示 / 100% 紅色。
 */
export function QuotaProgress() {
  const { data, isLoading, error, refetch } = useMyQuota();
  if (isLoading) return <LoadingSkeleton rows={1} />;
  if (error || !data) {
    return (
      <ErrorState
        title="配額資訊載入失敗"
        variant="inline"
        onRetry={refetch}
        error={error}
      />
    );
  }

  const used = new BigNumber(data.used_usd);
  const limit = new BigNumber(data.limit_usd);
  const pct = Math.min(data.percentage || 0, 100);

  const tone =
    pct >= 100
      ? "text-destructive [&_[data-progress-fill]]:bg-destructive"
      : pct >= 80
        ? "text-warning [&_[data-progress-fill]]:bg-warning"
        : "text-success [&_[data-progress-fill]]:bg-success";

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-muted-foreground">本月 LLM 用量</span>
        <span className={cn("num text-sm font-medium", tone)}>
          US${used.toFormat(2)} / US${limit.toFormat(2)}
        </span>
      </div>
      <Progress value={pct} className={cn(tone)} />
      <p className="text-xs text-muted-foreground">
        {pct >= 100
          ? "已超出本月配額，新增分析將被擋下"
          : pct >= 80
            ? "已接近本月配額上限"
            : `已使用 ${pct.toFixed(1)}%`}
      </p>
    </div>
  );
}

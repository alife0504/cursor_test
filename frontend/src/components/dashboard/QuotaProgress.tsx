"use client";

import BigNumber from "bignumber.js";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { Progress } from "@/components/ui/progress";
import { useMyQuota } from "@/hooks/useQuota";
import { cn } from "@/lib/utils";

// Phase 16 § B:儀表板 — LLM 月用量 progress bar
//   - 80% 警示色;100% 紅色
export function QuotaProgress() {
  const { data, isLoading, error } = useMyQuota();
  if (isLoading) return <LoadingSkeleton rows={1} />;
  if (error || !data)
    return <p className="text-sm text-destructive">配額資訊載入失敗</p>;

  const used = new BigNumber(data.used_usd);
  const limit = new BigNumber(data.limit_usd);
  const pct = Math.min(data.percentage || 0, 100);

  const tone =
    pct >= 100
      ? "text-rose-600 [&_[data-progress-fill]]:bg-rose-600"
      : pct >= 80
        ? "text-amber-600 [&_[data-progress-fill]]:bg-amber-600"
        : "text-emerald-600 [&_[data-progress-fill]]:bg-emerald-600";

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-muted-foreground">本月 LLM 用量</span>
        <span className={cn("text-sm font-medium tabular-nums", tone)}>
          US${used.toFormat(2)} / US${limit.toFormat(2)}
        </span>
      </div>
      <Progress value={pct} className={cn(tone)} />
      <p className="text-xs text-muted-foreground">
        {pct >= 100
          ? "已超出本月配額,新增分析將被擋下"
          : pct >= 80
            ? "已接近本月配額上限"
            : `已使用 ${pct.toFixed(1)}%`}
      </p>
    </div>
  );
}

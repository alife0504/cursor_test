"use client";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { useMarketOverview } from "@/hooks/useMarket";

// Phase 16 § B:大盤指數 mini chart
//   - v1.0:後端 P10 stub 回的 overview 還不一定含時間序列;
//     若沒有 chart data 則退化為「目前指數 + 漲跌家數」摘要。
//   - 接 lightweight-charts 的完整版留 P17。
export function MarketIndexMiniChart() {
  const { data, isLoading, error } = useMarketOverview("TW");

  if (isLoading) return <LoadingSkeleton rows={2} />;
  if (error) return <p className="text-sm text-destructive">無法載入大盤</p>;
  if (!data) return null;

  const adv = (data.advancers as number | undefined) ?? null;
  const dec = (data.decliners as number | undefined) ?? null;
  const unc = (data.unchanged as number | undefined) ?? null;
  const idxObj = (data.index ?? null) as Record<string, unknown> | null;
  const idxValue = idxObj?.close ?? idxObj?.value ?? null;
  const idxChange = idxObj?.change_pct ?? idxObj?.change ?? null;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-muted-foreground">加權指數</span>
        <span className="text-lg font-semibold tabular-nums">
          {idxValue !== null && idxValue !== undefined ? String(idxValue) : "-"}
        </span>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground tabular-nums">
        <span>
          漲 <span className="text-emerald-600">{adv ?? "-"}</span> ·
          {" "}跌 <span className="text-rose-600">{dec ?? "-"}</span> ·
          {" "}平 {unc ?? "-"}
        </span>
        <span>{idxChange !== null && idxChange !== undefined ? `${idxChange}` : ""}</span>
      </div>
    </div>
  );
}

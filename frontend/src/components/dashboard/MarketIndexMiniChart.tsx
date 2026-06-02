"use client";

import { useMemo, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PriceDelta } from "@/components/common/PriceDelta";
import { Sparkline } from "@/components/common/Sparkline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMarketOverview } from "@/hooks/useMarket";
import { useOhlcv } from "@/hooks/useStocks";
import { cn } from "@/lib/utils";

function isoDate(daysAgo: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

/**
 * 真正的大盤趨勢圖：
 * - 7 / 30 / 90 日 切換
 * - 失敗時 graceful fallback：純文字摘要
 * - 用 TAIEX symbol 從後端拉 OHLCV
 */
export function MarketIndexMiniChart() {
  const [range, setRange] = useState<7 | 30 | 90>(30);
  const start = isoDate(range);
  const end = isoDate(0);

  const overview = useMarketOverview("TW");
  const ohlcv = useOhlcv({ symbol: "TAIEX", start, end });

  const idxObj = (overview.data?.index ?? null) as Record<string, unknown> | null;
  const idxClose =
    (idxObj?.twse_close ?? idxObj?.close ?? idxObj?.value ?? null) as
      | string
      | number
      | null;
  const idxChange =
    (idxObj?.twse_change_pct ?? idxObj?.change_pct ?? null) as
      | string
      | number
      | null;

  const series = useMemo(() => {
    return (ohlcv.data ?? [])
      .map((p) => Number(p.close))
      .filter((n) => Number.isFinite(n));
  }, [ohlcv.data]);

  const tone =
    idxChange !== null && Number(idxChange) > 0
      ? "bull"
      : idxChange !== null && Number(idxChange) < 0
        ? "bear"
        : "flat";

  const adv = (overview.data?.advancers as number | undefined) ?? null;
  const dec = (overview.data?.decliners as number | undefined) ?? null;
  const unc = (overview.data?.unchanged as number | undefined) ?? null;

  if (overview.isLoading) return <LoadingSkeleton rows={3} />;
  if (overview.error) {
    return (
      <ErrorState
        title="大盤資料載入失敗"
        variant="inline"
        onRetry={overview.refetch}
        error={overview.error}
      />
    );
  }
  if (!overview.data) return null;

  const hasSpark = series.length > 2;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground">加權指數</p>
          <p className="num text-2xl font-bold leading-tight">
            {idxClose !== null && idxClose !== undefined
              ? String(idxClose)
              : "—"}
          </p>
          <PriceDelta
            value={idxChange}
            mode="raw"
            className="mt-1 text-sm"
          />
        </div>
        <div className="flex gap-1">
          {([7, 30, 90] as const).map((d) => (
            <Button
              key={d}
              size="xs"
              variant={range === d ? "default" : "outline"}
              onClick={() => setRange(d)}
              className="h-7 px-2 text-[11px]"
            >
              {d}D
            </Button>
          ))}
        </div>
      </div>

      <div className={cn("rounded-md border bg-muted/20 p-2")}>
        {ohlcv.isLoading ? (
          <div className="h-[80px] animate-pulse rounded bg-muted/40" />
        ) : hasSpark ? (
          <Sparkline data={series} tone={tone} height={80} />
        ) : (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">
            尚未有指數時間序列資料
            <br />
            （後端執行 <code className="font-mono">make backfill ARGS=&quot;--symbol TAIEX&quot;</code> 即可顯示）
          </p>
        )}
      </div>

      <dl className="grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-md border bg-card p-2 text-center">
          <dt className="text-muted-foreground">上漲</dt>
          <dd className="num mt-0.5 font-semibold text-bull">{adv ?? "—"}</dd>
        </div>
        <div className="rounded-md border bg-card p-2 text-center">
          <dt className="text-muted-foreground">下跌</dt>
          <dd className="num mt-0.5 font-semibold text-bear">{dec ?? "—"}</dd>
        </div>
        <div className="rounded-md border bg-card p-2 text-center">
          <dt className="text-muted-foreground">平盤</dt>
          <dd className="num mt-0.5 font-semibold text-flat">{unc ?? "—"}</dd>
        </div>
      </dl>

      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <Badge variant="outline" className="text-[10px]">
          資料源 TWSE / TPEX
        </Badge>
        <span>對應 {range} 日走勢</span>
      </div>
    </div>
  );
}

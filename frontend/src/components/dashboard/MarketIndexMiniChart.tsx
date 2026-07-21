"use client";

import { useMemo, useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PriceDelta } from "@/components/common/PriceDelta";
import { Sparkline } from "@/components/common/Sparkline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  useMarketOverview,
  useRealtimeIndex,
  useRealtimeOverview,
} from "@/hooks/useMarket";
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
  // 盤中即時漲跌家數（每 5 秒；收盤自動停輪詢、退回盤後值）
  const rtOverview = useRealtimeOverview(true);
  const ohlcv = useOhlcv({ symbol: "TAIEX", start, end });
  // 盤中即時加權指數（收盤後自動停輪詢，退回盤後/OHLCV 推導值）
  const rtIndex = useRealtimeIndex();
  const rtTaiex = rtIndex.data?.available
    ? rtIndex.data.quotes?.find((q) => q.symbol === "TAIEX")
    : undefined;
  const liveAt =
    rtTaiex?.price != null && rtIndex.data?.as_of
      ? rtIndex.data.as_of.slice(11, 19)
      : null;

  // 後端 overview 回 indices（複數陣列）；取 TAIEX 攤平。原讀單數 overview.data?.index
  // 恆為 null（欄位名打錯）→ 後端算好的指數報價從未被採用。
  const taiexQuote = (overview.data?.indices ?? []).find((q) => q.symbol === "TAIEX");
  const idxObj: Record<string, unknown> | null = taiexQuote
    ? { twse_close: taiexQuote.close ?? null, twse_change_pct: taiexQuote.change_pct ?? null }
    : null;

  const series = useMemo(() => {
    return (ohlcv.data ?? [])
      .map((p) => Number(p.close))
      .filter((n) => Number.isFinite(n));
  }, [ohlcv.data]);

  // 優先用後端 indices 的指數報價；缺時從 OHLCV 序列推導
  // （close = 最後一筆、漲跌% = 區間首尾變化，對應所選 N 日）。
  const backendClose = (idxObj?.twse_close ??
    idxObj?.close ??
    idxObj?.value ??
    null) as string | number | null;
  const backendChange = (idxObj?.twse_change_pct ??
    idxObj?.change_pct ??
    null) as string | number | null;
  const seriesClose = series.length ? series[series.length - 1] : null;
  // 優先序：盤中即時 > 後端盤後 close > OHLCV 序列末值
  const idxClose: string | number | null =
    rtTaiex?.price != null
      ? Number(rtTaiex.price).toLocaleString("en-US", {
          maximumFractionDigits: 2,
        })
      : (backendClose ??
        (seriesClose !== null
          ? seriesClose.toLocaleString("en-US", { maximumFractionDigits: 2 })
          : null));
  const idxChange: string | number | null =
    rtTaiex?.change_rate != null
      ? Number(rtTaiex.change_rate)
      : (backendChange ??
        (series.length >= 2 && series[0] !== 0
          ? ((series[series.length - 1] - series[0]) / series[0]) * 100
          : null));

  const tone =
    idxChange !== null && Number(idxChange) > 0
      ? "bull"
      : idxChange !== null && Number(idxChange) < 0
        ? "bear"
        : "flat";

  // 漲跌家數：盤中優先用即時層（與 /market/overview 同一份即時快照），取不到才退回盤後。
  // 原本只讀 overview（零輪詢）→ 盤中進頁後整場不會變，且與市場總覽頁的數字對不起來。
  const rtBreadth = rtOverview.data;
  // 後端欄位是 advance_count / decline_count / unchanged_count（舊名作 fallback）
  const adv = (rtBreadth?.advance_count ??
    overview.data?.advance_count ??
    overview.data?.advancers ??
    null) as number | null;
  const dec = (rtBreadth?.decline_count ??
    overview.data?.decline_count ??
    overview.data?.decliners ??
    null) as number | null;
  const unc = (rtBreadth?.unchanged_count ??
    overview.data?.unchanged_count ??
    overview.data?.unchanged ??
    null) as number | null;

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
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            加權指數
            {liveAt ? (
              <span className="num text-[10px] text-bull/80">即時 · {liveAt}</span>
            ) : null}
          </p>
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
            （執行 <code className="font-mono">make seed-index ARGS=&quot;--yes&quot;</code> 寫入大盤 OHLCV 即可顯示）
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

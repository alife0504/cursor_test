"use client";

import { useMemo, useState } from "react";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { cn } from "@/lib/utils";
import type { HeatmapResponse } from "@/lib/api-types";

type Mode = "chg" | "flow";

// 每產業最多顯示檔數；每格最低高度（px）——設地板保證「名稱＋代號＋漲跌%」都看得清楚，
// 巨頭（如台積電）再大也不會把同欄小格壓成看不見的細條。
const TOP_N = 12;
const MIN_TILE_H = 44;
// 最多顯示幾大產業。欄寬＝成交值比例（flex-grow），需要留白給 grow 才能讓大產業真的更寬；
// 欄數太多會全部卡在 min-width、爆版橫向捲動、變成等寬窄條（就是「擠在一起」）。
// 10 欄在 ~960px 容器有足夠留白 → 半導體等大產業明顯更寬，treemap 比例才讀得出來。
const MAX_INDUSTRIES = 10;
const MIN_COL_W = 66;

/** 熱力圖配色（紅漲綠跌）。chg：%，±3% 到滿色；flow：億，±30 億到滿色。 */
function heatColor(v: number, mode: Mode): string {
  const scale = mode === "chg" ? 3 : 30;
  const m = Math.min(1, Math.abs(v) / scale);
  if (v > 0) return `rgba(224,56,75,${(0.24 + 0.66 * m).toFixed(3)})`; // 紅＝漲/買超
  if (v < 0) return `rgba(15,157,99,${(0.22 + 0.64 * m).toFixed(3)})`; // 綠＝跌/賣超
  return "rgba(148,161,178,.35)";
}

function fmtMetric(v: number, mode: Mode): string {
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return mode === "chg" ? `${sign}${Math.abs(v).toFixed(2)}%` : `${sign}${Math.abs(v).toFixed(1)}億`;
}
function fmtYi(n: number): string {
  return `${(n / 1e8).toLocaleString("en-US", { maximumFractionDigits: 0 })} 億`;
}

export function SectorHeatmap({
  data,
  isLoading,
}: {
  data?: HeatmapResponse;
  isLoading?: boolean;
}) {
  const [mode, setMode] = useState<Mode>("chg");

  const industries = useMemo(() => {
    const list = data?.industries ?? [];
    // 直欄並排（產業當欄、股票欄內垂直疊）；欄寬／格高以成交值為權重（兩模式一致 →
    // 切換時格子不跳，只換配色/標籤）。取前 N 大產業，欄少才寬、比例才讀得出來。
    return list.filter((i) => i.value > 0 && i.stocks.length > 0).slice(0, MAX_INDUSTRIES);
  }, [data]);

  // 板塊圖總高＝隨「最擠的那一欄檔數」往下延伸，讓每格都有 ~64px 呼吸空間、且不低於地板。
  // 這樣值小的個股也能完整顯示名稱與漲跌%，而非被壓成細條。
  const boardH = useMemo(() => {
    const maxTiles = industries.reduce((m, i) => Math.max(m, Math.min(i.stocks.length, TOP_N)), 1);
    return Math.min(1120, Math.max(560, maxTiles * 64 + 8));
  }, [industries]);

  const liveLabel =
    mode === "flow"
      ? "資金流 · 盤後 19:30 / 21:30 更新"
      : data?.realtime
        ? "即時 · 每 5 秒更新"
        : "收盤";

  return (
    <section className="rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <h3 className="text-sm font-medium">市場板塊圖</h3>
        <div className="inline-flex rounded-md border bg-muted/50 p-0.5">
          {(
            [
              ["chg", "即時漲跌"],
              ["flow", "資金流(億)"],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                "rounded px-2.5 py-1 text-xs transition-colors",
                mode === m
                  ? "bg-card font-semibold text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-2.5">
        {isLoading && !data ? (
          <LoadingSkeleton rows={6} />
        ) : industries.length === 0 ? (
          <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
            尚無板塊資料
          </div>
        ) : (
          <div className="flex gap-[4px] overflow-x-auto" style={{ height: boardH }}>
            {industries.map((ind) => (
              <div
                key={ind.name}
                className="flex flex-col overflow-hidden"
                style={{ flex: ind.value, minWidth: MIN_COL_W }}
              >
                <div className="flex items-baseline justify-between gap-1 px-1 pb-1 text-[12px] font-semibold text-foreground/90">
                  <span className="truncate">{ind.name}</span>
                  <span className="num shrink-0 tabular-nums text-[10px] font-normal text-muted-foreground">
                    {mode === "flow"
                      ? `${ind.flow_total > 0 ? "+" : ind.flow_total < 0 ? "−" : ""}${Math.abs(ind.flow_total).toFixed(1)}億`
                      : fmtYi(ind.value)}
                  </span>
                </div>
                <div className="flex min-h-0 flex-1 flex-col gap-[3px]">
                  {ind.stocks.slice(0, TOP_N).map((s) => {
                    const v = mode === "chg" ? s.chg : s.flow;
                    return (
                      <div
                        key={s.symbol}
                        className="flex min-h-0 flex-col justify-center overflow-hidden rounded-md px-2 py-1 text-white"
                        style={{ flex: s.value, minHeight: MIN_TILE_H, background: heatColor(v, mode) }}
                        title={`${s.symbol} ${s.name}｜漲跌 ${fmtMetric(s.chg, "chg")}｜資金流 ${fmtMetric(s.flow, "flow")}｜成交值 ${fmtYi(s.value)}`}
                      >
                        {/* 完整中文名稱（FinMind）；min-height 地板保證整名＋代號＋漲跌%都放得下 */}
                        <div className="truncate text-[13px] font-bold leading-tight">{s.name}</div>
                        <div className="mt-0.5 flex items-center justify-between gap-1 text-[11px] leading-tight opacity-95">
                          <span className="num tabular-nums">{s.symbol}</span>
                          <span className="num font-bold tabular-nums">{fmtMetric(v, mode)}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t px-4 py-2 text-[11px] text-muted-foreground">
        <span>
          {mode === "chg"
            ? "格子大小＝成交值 · 顏色＝漲跌%"
            : "格子大小＝成交值 · 顏色＝三大法人當日淨額（紅買超 / 綠賣超）"}
        </span>
        <span className="ml-auto">{liveLabel}</span>
      </div>
    </section>
  );
}

"use client";

import { useMemo } from "react";

import { cn } from "@/lib/utils";
import type { IntradayResponse } from "@/lib/api-types";

// 紅漲綠跌
const BULL = "rgb(224,56,75)";
const BEAR = "rgb(15,157,99)";
const FLAT = "rgb(148,161,178)";

function fmt0(n: number | null | undefined): string {
  return n == null ? "—" : Math.round(n).toLocaleString("en-US");
}
function fmt2(n: number | null | undefined): string {
  return n == null ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * 盤中即時走勢圖（加權指數 5 秒序列 / 台指全逐筆）。
 * 標記：平盤（前收，虛線）、最高、最低（虛線＋標籤）、當下（端點圓點＋抬頭數字），
 * 漲停 / 跌停（多在可視範圍外，列於底部標籤；台指全為真實漲跌停、指數為 ±10% 參考）。
 */
export function IntradayChart({
  data,
  name,
  isLoading,
}: {
  data?: IntradayResponse;
  name: string;
  isLoading?: boolean;
}) {
  const cur = data?.current ?? null;
  const prev = data?.prev_close ?? null;
  const chg = data?.change ?? null;
  const chgRate = data?.change_rate ?? null;
  const tone = chg == null || chg === 0 ? "flat" : chg > 0 ? "bull" : "bear";
  const color = tone === "bull" ? BULL : tone === "bear" ? BEAR : FLAT;

  const chart = useMemo(() => {
    const series = data?.series ?? [];
    if (series.length < 2) return null;
    const W = 600;
    const H = 200;
    const padL = 8;
    const padR = 66;
    const padT = 14;
    const padB = 22;
    const x0 = padL;
    const x1 = W - padR;
    const y0 = padT;
    const y1 = H - padB;

    const prices = series.map((p) => p.price);
    const hi = data?.high ?? Math.max(...prices);
    const lo = data?.low ?? Math.min(...prices);
    const anchors = [hi, lo, prev].filter((v): v is number => v != null);
    let yMin = Math.min(...anchors);
    let yMax = Math.max(...anchors);
    let range = yMax - yMin;
    if (range <= 0) range = Math.abs(yMax) * 0.01 || 1;
    const pad = range * 0.08;
    yMin -= pad;
    yMax += pad;

    const sx = (i: number) => x0 + (i / (series.length - 1)) * (x1 - x0);
    const sy = (p: number) => y1 - ((p - yMin) / (yMax - yMin)) * (y1 - y0);

    const line = series.map((p, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(p.price).toFixed(1)}`).join("");
    const area = `${line}L${sx(series.length - 1).toFixed(1)},${y1}L${x0},${y1}Z`;

    const inRange = (v: number | null | undefined) => v != null && v >= yMin && v <= yMax;

    return {
      W, H, x0, x1, y0, y1,
      line, area,
      sx, sy,
      hi, lo,
      curX: sx(series.length - 1),
      curY: cur != null ? sy(cur) : sy(prices[prices.length - 1]),
      prevY: prev != null ? sy(prev) : null,
      hiY: sy(hi),
      loY: sy(lo),
      firstT: series[0].time.slice(0, 5),
      lastT: series[series.length - 1].time.slice(0, 5),
      showPrev: inRange(prev),
    };
  }, [data, cur, prev]);

  return (
    <div className="flex flex-col rounded-lg border bg-card p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-xs font-medium text-muted-foreground">{name}</h4>
        <div className="flex items-baseline gap-1.5">
          <span className="num text-base font-bold tabular-nums leading-none">{fmt2(cur)}</span>
          <span
            className="num text-xs font-medium tabular-nums"
            style={{ color }}
          >
            {chg != null ? `${chg > 0 ? "+" : chg < 0 ? "−" : ""}${fmt0(Math.abs(chg))}` : "—"}
            {chgRate != null ? ` (${chg && chg > 0 ? "+" : chg && chg < 0 ? "−" : ""}${Math.abs(chgRate).toFixed(2)}%)` : ""}
          </span>
        </div>
      </div>

      {isLoading && !data ? (
        <div className="mt-2 h-[150px] animate-pulse rounded bg-muted/40" />
      ) : !chart ? (
        <div className="mt-2 flex h-[150px] items-center justify-center text-xs text-muted-foreground">
          尚無盤中走勢資料
        </div>
      ) : (
        <svg viewBox={`0 0 ${chart.W} ${chart.H}`} className="mt-1.5 h-auto w-full" role="img">
          <defs>
            <linearGradient id={`ig-${data?.symbol}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.28" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* 平盤（前收）虛線 */}
          {chart.showPrev && chart.prevY != null ? (
            <>
              <line x1={chart.x0} y1={chart.prevY} x2={chart.x1} y2={chart.prevY} stroke={FLAT} strokeWidth="1" strokeDasharray="4 3" opacity="0.7" />
              <text x={chart.x1 + 2} y={chart.prevY + 3} fontSize="9" fill={FLAT}>平盤 {fmt0(prev)}</text>
            </>
          ) : null}

          {/* 最高 / 最低 虛線 + 標籤 */}
          <line x1={chart.x0} y1={chart.hiY} x2={chart.x1} y2={chart.hiY} stroke={BULL} strokeWidth="0.8" strokeDasharray="2 3" opacity="0.5" />
          <text x={chart.x0 + 2} y={chart.hiY - 2.5} fontSize="8.5" fill={BULL} opacity="0.9">高 {fmt0(chart.hi)}</text>
          <line x1={chart.x0} y1={chart.loY} x2={chart.x1} y2={chart.loY} stroke={BEAR} strokeWidth="0.8" strokeDasharray="2 3" opacity="0.5" />
          <text x={chart.x0 + 2} y={chart.loY + 8} fontSize="8.5" fill={BEAR} opacity="0.9">低 {fmt0(chart.lo)}</text>

          {/* 面積 + 走勢線 */}
          <path d={chart.area} fill={`url(#ig-${data?.symbol})`} />
          <path d={chart.line} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round" />

          {/* 當下端點 */}
          <line x1={chart.curX} y1={chart.y0} x2={chart.curX} y2={chart.y1} stroke={color} strokeWidth="0.6" opacity="0.35" />
          <circle cx={chart.curX} cy={chart.curY} r="2.6" fill={color} />
          <text x={chart.x1 + 2} y={chart.curY + 3} fontSize="9.5" fontWeight="700" fill={color}>{fmt0(cur)}</text>

          {/* 時間軸 */}
          <text x={chart.x0} y={chart.H - 6} fontSize="8.5" fill={FLAT}>{chart.firstT}</text>
          <text x={chart.x1} y={chart.H - 6} fontSize="8.5" fill={FLAT} textAnchor="end">{chart.lastT}</text>
        </svg>
      )}

      {/* 漲停 / 跌停（多在可視範圍外，列此）＋平盤，色卡標示 */}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t pt-2 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-[2px]" style={{ background: BULL }} />
          {data?.has_limit ? "漲停" : "＋10%"} {fmt0(data?.limit_up)}
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-[2px]" style={{ background: BEAR }} />
          {data?.has_limit ? "跌停" : "−10%"} {fmt0(data?.limit_down)}
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-[2px]" style={{ background: FLAT }} />
          平盤 {fmt0(prev)}
        </span>
        <span className={cn("ml-auto", data?.has_limit ? "" : "text-muted-foreground/70")}>
          {data?.has_limit ? "台指全 · 逐筆" : "加權 · 5 秒"}
        </span>
      </div>
    </div>
  );
}

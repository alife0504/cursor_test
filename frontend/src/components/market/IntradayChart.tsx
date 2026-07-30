"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { IntradayResponse } from "@/lib/api-types";

// 紅漲綠跌
const BULL = "rgb(224,56,75)";
const BEAR = "rgb(15,157,99)";
const FLAT = "rgb(148,161,178)";
const AMBER = "rgb(217,151,44)"; // 日盤高低參考線

function fmt0(n: number | null | undefined): string {
  return n == null ? "—" : Math.round(n).toLocaleString("en-US");
}
function fmt2(n: number | null | undefined): string {
  return n == null
    ? "—"
    : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * 盤中即時走勢圖（加權指數 5 秒序列 / 台指全逐筆）。SVG 依容器實際大小填滿（放大到滿格）。
 * 標記：平盤（前收，虛線）、當日最高、當日最低（虛線＋標籤）、當下（端點圓點＋抬頭數字）。
 * 加權指數與台指全皆無漲跌停，故不畫漲跌停。
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
  // 台指全：日盤/夜盤標示；加權：現貨
  const source =
    data?.symbol === "TXF"
      ? data?.phase === "night"
        ? "夜盤"
        : data?.phase === "day"
          ? "日盤"
          : "台指全"
      : "現貨";

  // 量測繪圖區容器 → SVG 依實際 px 尺寸繪製（填滿、文字不變形）
  const roRef = useRef<ResizeObserver | null>(null);
  const elRef = useRef<HTMLDivElement | null>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const measure = useCallback(() => {
    const el = elRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const w = el.clientWidth || Math.round(r.width);
    const h = el.clientHeight || Math.round(r.height);
    if (w > 0 && h > 0) setBox((p) => (p.w === w && p.h === h ? p : { w, h }));
  }, []);
  const setRef = useCallback(
    (el: HTMLDivElement | null) => {
      roRef.current?.disconnect();
      roRef.current = null;
      elRef.current = el;
      if (!el || typeof ResizeObserver === "undefined") return;
      const ro = new ResizeObserver(() => measure());
      ro.observe(el);
      roRef.current = ro;
      // 連續量測數幀直到版面穩定：mount 當下容器常是 min-height 的過渡尺寸（如 132×140），
      // 之後才撐到真實大小；此瀏覽器 ResizeObserver 不一定補觸發，故不能在拿到第一個非零值就停。
      let tries = 0;
      const attempt = () => {
        measure();
        if (tries++ < 14 && typeof requestAnimationFrame !== "undefined") {
          requestAnimationFrame(attempt);
        }
      };
      attempt();
    },
    [measure],
  );
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  const chart = useMemo(() => {
    const series = data?.series ?? [];
    const W = box.w;
    const H = box.h;
    if (series.length < 2 || W <= 0 || H <= 0) return null;
    const padR = 60; // 右側留給當下數字
    const padT = 12;
    const padB = 18; // 底部時間軸
    const x0 = 6;
    const x1 = W - padR;
    const y0 = padT;
    const y1 = H - padB;

    const prices = series.map((p) => p.price);
    const hi = data?.high ?? Math.max(...prices);
    const lo = data?.low ?? Math.min(...prices);
    // 日盤高低（台指全夜盤時作參考線）
    const showDay = !!data?.show_day_hl && data?.day_high != null && data?.day_low != null;
    const dayHi = showDay ? (data?.day_high as number) : null;
    const dayLo = showDay ? (data?.day_low as number) : null;
    const anchors = [hi, lo, prev, dayHi, dayLo].filter((v): v is number => v != null);
    let yMin = Math.min(...anchors);
    let yMax = Math.max(...anchors);
    let range = yMax - yMin;
    if (range <= 0) range = Math.abs(yMax) * 0.01 || 1;
    const pad = range * 0.08;
    yMin -= pad;
    yMax += pad;

    const sx = (i: number) => x0 + (i / (series.length - 1)) * (x1 - x0);
    const sy = (p: number) => y1 - ((p - yMin) / (yMax - yMin)) * (y1 - y0);

    const line = series
      .map((p, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(p.price).toFixed(1)}`)
      .join("");
    const area = `${line}L${sx(series.length - 1).toFixed(1)},${y1}L${x0},${y1}Z`;
    const inRange = (v: number | null | undefined) => v != null && v >= yMin && v <= yMax;

    return {
      W, H, x0, x1, y0, y1, line, area,
      curX: sx(series.length - 1),
      curY: cur != null ? sy(cur) : sy(prices[prices.length - 1]),
      prevY: prev != null ? sy(prev) : null,
      hiY: sy(hi), loY: sy(lo), hi, lo,
      dayHi, dayLo,
      dayHiY: dayHi != null ? sy(dayHi) : null,
      dayLoY: dayLo != null ? sy(dayLo) : null,
      firstT: series[0].time.slice(0, 5),
      lastT: series[series.length - 1].time.slice(0, 5),
      showPrev: inRange(prev),
    };
  }, [data, box, cur, prev]);

  return (
    <div className="flex h-full flex-col rounded-lg border bg-card p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="flex items-baseline gap-1.5 text-xs font-medium text-muted-foreground">
          {name}
          <span className="text-[10px] text-muted-foreground/60">{source}</span>
        </h4>
        <div className="flex items-baseline gap-1.5">
          <span className="num text-lg font-bold leading-none tabular-nums">{fmt2(cur)}</span>
          <span className="num text-xs font-medium tabular-nums" style={{ color }}>
            {chg != null ? `${chg > 0 ? "+" : chg < 0 ? "−" : ""}${fmt0(Math.abs(chg))}` : "—"}
            {chgRate != null
              ? ` (${chg && chg > 0 ? "+" : chg && chg < 0 ? "−" : ""}${Math.abs(chgRate).toFixed(2)}%)`
              : ""}
          </span>
        </div>
      </div>

      {/* 繪圖區：flex-1 撐滿卡片剩餘高度；ref 量測後 SVG 依 px 尺寸填滿 */}
      <div ref={setRef} className="relative mt-2 min-h-[140px] flex-1">
        {isLoading && !data ? (
          <div className="h-full w-full animate-pulse rounded bg-muted/40" />
        ) : !chart ? (
          <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
            尚無盤中走勢資料
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${chart.W} ${chart.H}`}
            width={chart.W}
            height={chart.H}
            className="absolute inset-0"
            role="img"
          >
            <defs>
              <linearGradient id={`ig-${data?.symbol}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity="0.26" />
                <stop offset="100%" stopColor={color} stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* 平盤（前收）虛線 */}
            {chart.showPrev && chart.prevY != null ? (
              <>
                <line x1={chart.x0} y1={chart.prevY} x2={chart.x1} y2={chart.prevY} stroke={FLAT} strokeWidth="1" strokeDasharray="4 3" opacity="0.75" />
                <text x={chart.x1 + 3} y={chart.prevY + 3} fontSize="10" fill={FLAT}>平盤 {fmt0(prev)}</text>
              </>
            ) : null}

            {/* 當日（全時段）最高 / 最低 虛線 + 標籤 */}
            <line x1={chart.x0} y1={chart.hiY} x2={chart.x1} y2={chart.hiY} stroke={BULL} strokeWidth="0.9" strokeDasharray="3 3" opacity="0.55" />
            <text x={chart.x1 + 3} y={chart.hiY + 3} fontSize="10" fill={BULL} opacity="0.95">高 {fmt0(chart.hi)}</text>
            <line x1={chart.x0} y1={chart.loY} x2={chart.x1} y2={chart.loY} stroke={BEAR} strokeWidth="0.9" strokeDasharray="3 3" opacity="0.55" />
            <text x={chart.x1 + 3} y={chart.loY + 3} fontSize="10" fill={BEAR} opacity="0.95">低 {fmt0(chart.lo)}</text>

            {/* 日盤最高 / 最低（台指全夜盤時的參考線，琥珀色點虛線） */}
            {chart.dayHiY != null ? (
              <>
                <line x1={chart.x0} y1={chart.dayHiY} x2={chart.x1} y2={chart.dayHiY} stroke={AMBER} strokeWidth="0.9" strokeDasharray="1 3" opacity="0.7" />
                <text x={chart.x1 + 3} y={chart.dayHiY + 3} fontSize="9.5" fill={AMBER}>日高 {fmt0(chart.dayHi)}</text>
              </>
            ) : null}
            {chart.dayLoY != null ? (
              <>
                <line x1={chart.x0} y1={chart.dayLoY} x2={chart.x1} y2={chart.dayLoY} stroke={AMBER} strokeWidth="0.9" strokeDasharray="1 3" opacity="0.7" />
                <text x={chart.x1 + 3} y={chart.dayLoY + 3} fontSize="9.5" fill={AMBER}>日低 {fmt0(chart.dayLo)}</text>
              </>
            ) : null}

            {/* 面積 + 走勢線 */}
            <path d={chart.area} fill={`url(#ig-${data?.symbol})`} />
            <path d={chart.line} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />

            {/* 當下端點 */}
            <line x1={chart.curX} y1={chart.y0} x2={chart.curX} y2={chart.y1} stroke={color} strokeWidth="0.7" opacity="0.3" />
            <circle cx={chart.curX} cy={chart.curY} r="3" fill={color} />
            <text x={chart.x1 + 3} y={chart.curY - 4} fontSize="11" fontWeight="700" fill={color}>{fmt0(cur)}</text>

            {/* 時間軸 */}
            <text x={chart.x0} y={chart.H - 5} fontSize="9.5" fill={FLAT}>{chart.firstT}</text>
            <text x={chart.x1} y={chart.H - 5} fontSize="9.5" fill={FLAT} textAnchor="end">{chart.lastT}</text>
          </svg>
        )}
      </div>
    </div>
  );
}

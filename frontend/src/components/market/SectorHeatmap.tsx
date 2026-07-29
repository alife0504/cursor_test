"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { cn } from "@/lib/utils";
import type { HeatmapResponse } from "@/lib/api-types";

type Mode = "chg" | "flow";

// 面積權重壓縮：台積電等成交值極大者照真實面積會過度膨脹。用 0.8 次方輕度壓縮 →
// 保留「越大＝成交越熱」的順序，但巨頭不霸佔整張圖、中小格更好讀。
// （squarified treemap 本身已把巨頭排成接近正方而非超寬長條，故只需輕壓。）
// 純視覺；tooltip 與標籤仍顯示真實成交值。
const SIZE_EXP = 0.8;
const sizeWeight = (v: number) => (v > 0 ? v ** SIZE_EXP : 0);

// 顯示的產業數／每產業檔數：固定（完整內容不因螢幕小而縮減）。
const MAX_INDUSTRIES = 12;
const TOP_PER = 14;
// 最小畫布尺寸：容器比它小時出現捲軸（左右／上下拖曳），而非把格子縮到看不清。
// 容器比它大時畫布填滿容器（格子隨之放大）。
const MIN_CANVAS_W = 860;
const MIN_CANVAS_H = 470;

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Squarified treemap（Bruls/Huizing/van Wijk）：把 items 依權重鋪滿矩形，
 * 每格盡量接近正方形——這正是「左寬右擠」一維切欄的解法，巨頭變大方塊而非超寬長條。
 * 回傳每個 item 加上 {x,y,w,h}（像素）。
 */
function squarify<T>(
  items: T[],
  rect: Rect,
  valueOf: (item: T) => number,
): Array<T & Rect> {
  const vals = items.map(valueOf);
  const total = vals.reduce((a, b) => a + b, 0);
  if (!(total > 0) || !(rect.w > 0) || !(rect.h > 0) || items.length === 0) {
    return [];
  }
  const scale = (rect.w * rect.h) / total;
  const nodes = items.map((it, k) => ({ it, area: vals[k] * scale }));

  const out: Array<T & Rect> = [];
  let { x, y, w, h } = rect;
  let idx = 0;

  const worst = (row: { area: number }[], side: number): number => {
    let s = 0;
    let mx = -Infinity;
    let mn = Infinity;
    for (const r of row) {
      s += r.area;
      if (r.area > mx) mx = r.area;
      if (r.area < mn) mn = r.area;
    }
    const s2 = s * s;
    const side2 = side * side;
    return Math.max((side2 * mx) / s2, s2 / (side2 * mn));
  };

  while (idx < nodes.length) {
    const side = Math.min(w, h);
    const row: { it: T; area: number }[] = [];
    while (idx < nodes.length) {
      const cand = row.concat(nodes[idx]);
      if (row.length === 0 || worst(cand, side) <= worst(row, side)) {
        row.push(nodes[idx]);
        idx++;
      } else {
        break;
      }
    }
    const rowArea = row.reduce((a, r) => a + r.area, 0);
    const thick = rowArea / side;
    if (w >= h) {
      // 短邊是 h → 這一列排成一直行（寬 thick、沿高度 h 疊）
      let cy = y;
      for (const r of row) {
        const rh = r.area / thick;
        out.push({ ...(r.it as T), x, y: cy, w: thick, h: rh });
        cy += rh;
      }
      x += thick;
      w -= thick;
    } else {
      // 短邊是 w → 這一列排成一橫帶（高 thick、沿寬度 w 排）
      let cx = x;
      for (const r of row) {
        const rw = r.area / thick;
        out.push({ ...(r.it as T), x: cx, y, w: rw, h: thick });
        cx += rw;
      }
      y += thick;
      h -= thick;
    }
  }
  return out;
}

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

interface HeatStock {
  symbol: string;
  name: string;
  chg: number;
  flow: number;
  value: number;
}
interface HeatIndustry {
  name: string;
  value: number;
  flow_total: number;
  stocks: HeatStock[];
}

export function SectorHeatmap({
  data,
  isLoading,
}: {
  data?: HeatmapResponse;
  isLoading?: boolean;
}) {
  const [mode, setMode] = useState<Mode>("chg");

  // 量測容器寬度（響應式）：用 callback ref → 節點掛上（含資料載入後才渲染）即 observe，
  // 並立即量一次；只在寬度真的變才更新，避免重繪迴圈。
  // （用 useEffect([]) 會在資料未載入、board 尚未渲染時就跑掉且不重跑 → 永遠量不到寬度。）
  // 另掛 window resize 後備，確保拖曳縮放也即時重排。
  const roRef = useRef<ResizeObserver | null>(null);
  const elRef = useRef<HTMLDivElement | null>(null);
  // 量捲動視窗的「可視內容區」大小（clientWidth/Height 已排除捲軸與邊框）。
  const [view, setView] = useState({ w: 0, h: 0 });
  const measure = useCallback(() => {
    const el = elRef.current;
    if (!el) return;
    // 以 clientWidth/Height（內容區、已排除捲軸）為主 → 避免出現捲軸時內容區被吃掉又觸發
    // 另一方向的多餘捲軸；mount 時機 client 可能回 0，退回 getBoundingClientRect（會強制 reflow）。
    const r = el.getBoundingClientRect();
    const w = el.clientWidth || Math.round(r.width);
    const h = el.clientHeight || Math.round(r.height);
    if (w > 0 && h > 0) {
      setView((prev) => (prev.w === w && prev.h === h ? prev : { w, h }));
    }
  }, []);
  const setBoxRef = useCallback(
    (el: HTMLDivElement | null) => {
      roRef.current?.disconnect();
      roRef.current = null;
      elRef.current = el;
      if (!el || typeof ResizeObserver === "undefined") return;
      const ro = new ResizeObserver(() => measure());
      ro.observe(el);
      roRef.current = ro;
      measure();
      // 再於下一影格補量一次（mount 當下版面可能尚未完成）。
      if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(measure);
    },
    [measure],
  );
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  // 畫布尺寸＝視窗與最小尺寸取大者：夠大就填滿（格子放大）、不夠就出現捲軸可拖曳看完整。
  const canvasW = Math.max(view.w || 0, MIN_CANVAS_W);
  const canvasH = Math.max(view.h || 0, MIN_CANVAS_H);

  const layout = useMemo(() => {
    const W = canvasW;
    const H = canvasH;
    if (W <= 0 || H <= 0) return { tiles: [] as Array<HeatStock & Rect>, groups: [] as Array<{ name: string } & Rect> };
    const inds = ((data?.industries ?? []) as HeatIndustry[])
      .filter((i) => i.value > 0 && i.stocks.length > 0)
      .slice(0, MAX_INDUSTRIES);
    const outer = squarify(inds, { x: 0, y: 0, w: W, h: H }, (i) => sizeWeight(i.value));

    const tiles: Array<HeatStock & Rect> = [];
    const groups: Array<{ name: string } & Rect> = [];
    for (const g of outer) {
      groups.push({ name: g.name, x: g.x, y: g.y, w: g.w, h: g.h });
      const stocks = g.stocks.slice(0, TOP_PER);
      const inner = squarify(stocks, { x: g.x, y: g.y, w: g.w, h: g.h }, (s) => sizeWeight(s.value));
      for (const t of inner) tiles.push(t);
    }
    return { tiles, groups };
  }, [data, canvasW, canvasH]);

  const liveLabel =
    mode === "flow"
      ? "資金流 · 盤後 19:30 / 21:30 更新"
      : data?.realtime
        ? "即時 · 每 5 秒更新"
        : "收盤";

  const hasData = (data?.industries ?? []).length > 0;

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
        ) : !hasData ? (
          <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
            尚無板塊資料
          </div>
        ) : (
          <div
            ref={setBoxRef}
            className="overflow-auto rounded-md bg-muted/10 ring-1 ring-inset ring-border"
            style={{ height: "clamp(380px, 60vh, 680px)" }}
          >
            {/* 畫布：夠大就填滿容器、不夠就比容器大 → 外層 overflow-auto 出現左右／上下拖曳bar */}
            <div className="relative" style={{ width: canvasW, height: canvasH }}>
            {/* 個股方塊（squarified，接近正方；大小＝成交值、顏色＝漲跌/資金流） */}
            {layout.tiles.map((t) => {
              const v = mode === "chg" ? t.chg : t.flow;
              const tw = Math.max(0, t.w - 2);
              const th = Math.max(0, t.h - 2);
              const showName = tw >= 38 && th >= 26;
              const showMeta = tw >= 50 && th >= 42;
              return (
                <div
                  key={t.symbol}
                  className="absolute flex flex-col justify-center overflow-hidden rounded-[3px] text-white"
                  style={{ left: t.x, top: t.y, width: tw, height: th, background: heatColor(v, mode) }}
                  title={`${t.symbol} ${t.name}｜漲跌 ${fmtMetric(t.chg, "chg")}｜資金流 ${fmtMetric(t.flow, "flow")}｜成交值 ${fmtYi(t.value)}`}
                >
                  {showName ? (
                    <div className="truncate px-1 text-[12px] font-bold leading-none">{t.name}</div>
                  ) : null}
                  {showMeta ? (
                    <div className="mt-1 flex items-center justify-between gap-1 px-1 text-[10px] leading-none opacity-95">
                      <span className="num tabular-nums">{t.symbol}</span>
                      <span className="num font-bold tabular-nums">{fmtMetric(v, mode)}</span>
                    </div>
                  ) : showName ? (
                    <div className="num px-1 text-[10px] leading-none opacity-90">{fmtMetric(v, mode)}</div>
                  ) : null}
                </div>
              );
            })}

            {/* 產業框線（淡）＋ 產業名標籤（左上角小片，overlay） */}
            {layout.groups.map((g) => (
              <div
                key={`b-${g.name}`}
                aria-hidden
                className="pointer-events-none absolute rounded-[3px]"
                style={{
                  left: g.x,
                  top: g.y,
                  width: g.w,
                  height: g.h,
                  boxShadow: "inset 0 0 0 1.5px rgba(0,0,0,0.22)",
                }}
              />
            ))}
            {layout.groups.map((g) =>
              g.w >= 52 && g.h >= 20 ? (
                <div
                  key={`l-${g.name}`}
                  aria-hidden
                  className="pointer-events-none absolute"
                  style={{ left: g.x + 2, top: g.y + 2, maxWidth: g.w - 4 }}
                >
                  <span className="inline-block max-w-full truncate rounded bg-black/35 px-1 text-[10px] font-semibold text-white">
                    {g.name}
                  </span>
                </div>
              ) : null,
            )}
            </div>
          </div>
        )}
      </div>

      {/* 圖例：flex-wrap → 寬度夠一行、太窄自動往下折。大小＝成交值、顏色＝漲跌/資金流。 */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t px-4 py-2.5 text-[11px] text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-end gap-[3px]" aria-hidden>
            <span className="inline-block shrink-0 rounded-[2px] bg-muted-foreground/40" style={{ width: 7, height: 7 }} />
            <span className="inline-block shrink-0 rounded-[2px] bg-muted-foreground/40" style={{ width: 10, height: 10 }} />
            <span className="inline-block shrink-0 rounded-[2px] bg-muted-foreground/50" style={{ width: 13, height: 13 }} />
          </span>
          <span className="shrink-0">格子越大＝成交值越高（資金越集中）</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="shrink-0">{mode === "chg" ? "跌" : "賣超"}</span>
          <span
            className="inline-block h-2.5 w-24 shrink-0 rounded-full"
            style={{
              background: `linear-gradient(90deg, ${heatColor(mode === "chg" ? -3 : -30, mode)}, rgba(148,161,178,.35), ${heatColor(mode === "chg" ? 3 : 30, mode)})`,
            }}
          />
          <span className="shrink-0">{mode === "chg" ? "漲" : "買超"}</span>
          <span className="shrink-0 text-muted-foreground/70">
            {mode === "chg" ? "（±3% 到最濃）" : "（±30 億到最濃）"}
          </span>
        </div>
        <span className="ml-auto shrink-0">{liveLabel}</span>
      </div>
    </section>
  );
}

import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * 統一漲跌幅顯示元件（**台股慣例：紅漲綠跌**）。
 *
 * - value: 數值或字串（百分比格式請傳 0.012 表 1.2%；或傳 raw 數字 + suffix）
 * - mode: "pct" 預設加 % 號 + 兩位小數；"abs" 顯示原值；"both" 顯示變化值與變化率
 * - delta：點數變動（mode=both 時並陳）
 */
interface PriceDeltaProps {
  value?: number | string | null;
  delta?: number | string | null;
  /** "pct"：value 是 -1 ~ +∞ 的小數，會 × 100 顯示百分比；"raw"：value 已是百分比數字（如 +1.23）；"abs"：純數值 */
  mode?: "pct" | "raw" | "abs" | "both";
  /** 是否在前面加 +/− 號（預設 true） */
  showSign?: boolean;
  /** 顯示箭頭圖示（預設 true） */
  showIcon?: boolean;
  /** 小數位數（預設 pct/raw=2, abs=0） */
  decimals?: number;
  /** 數值前綴（如 NT$、US$） */
  prefix?: string;
  /** 數值後綴（如 股、口） */
  suffix?: string;
  className?: string;
}

function toNumber(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return n;
}

function tone(n: number | null): "bull" | "bear" | "flat" {
  if (n === null || n === 0) return "flat";
  return n > 0 ? "bull" : "bear";
}

export function PriceDelta({
  value,
  delta,
  mode = "raw",
  showSign = true,
  showIcon = true,
  decimals,
  prefix = "",
  suffix,
  className,
}: PriceDeltaProps) {
  const raw = toNumber(value);
  const deltaN = toNumber(delta);
  const t = tone(raw);

  const sufDefault = mode === "pct" || mode === "raw" || mode === "both" ? "%" : "";
  const sf = suffix ?? sufDefault;
  const dec =
    decimals ?? (mode === "pct" || mode === "raw" || mode === "both" ? 2 : 0);

  const displayN =
    raw === null ? null : mode === "pct" ? raw * 100 : raw;
  const sign = displayN === null ? "" : displayN > 0 ? "+" : displayN < 0 ? "−" : "";
  const numTxt =
    displayN === null
      ? "—"
      : `${prefix}${Math.abs(displayN).toFixed(dec)}${sf}`;

  return (
    <span
      data-tone={t}
      className={cn(
        "inline-flex items-center gap-1 num text-sm font-medium",
        t === "bull" && "text-bull",
        t === "bear" && "text-bear",
        t === "flat" && "text-flat",
        className,
      )}
    >
      {showIcon ? (
        t === "bull" ? (
          <TrendingUp className="h-3.5 w-3.5" aria-hidden />
        ) : t === "bear" ? (
          <TrendingDown className="h-3.5 w-3.5" aria-hidden />
        ) : (
          <Minus className="h-3.5 w-3.5" aria-hidden />
        )
      ) : null}
      <span>
        {showSign ? sign : ""}
        {numTxt}
      </span>
      {mode === "both" && deltaN !== null ? (
        <span className="text-xs text-muted-foreground">
          ({deltaN > 0 ? "+" : deltaN < 0 ? "−" : ""}
          {Math.abs(deltaN).toFixed(dec)})
        </span>
      ) : null}
    </span>
  );
}

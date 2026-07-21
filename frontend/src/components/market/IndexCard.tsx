import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// 大盤指數卡片（紅漲綠跌）
interface IndexCardProps {
  name: string;
  value?: string | number | null;
  /** 漲跌點數（對前一交易日收盤的絕對變化）。與 changePct 並列顯示。 */
  change?: string | number | null;
  changePct?: string | number | null;
  /** 卡片右上角小標（如「即時 13:25:01」或「收盤」）。固定佔一行高，讓多張卡片對齊。 */
  subtitle?: string | null;
  className?: string;
}

function fmtValue(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** 轉數字；非有限值一律回 null（讓呼叫端統一用 null 判斷有無）。 */
function toNum(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function IndexCard({
  name,
  value,
  change,
  changePct,
  subtitle,
  className,
}: IndexCardProps) {
  const num = toNum(changePct);
  const chg = toNum(change);
  // 方向以「有值者」判定：優先用漲跌%，缺就用點數（兩者同號，任一即可定紅綠）
  const dir = num ?? chg;
  const tone: "bull" | "bear" | "flat" =
    dir === null || dir === 0 ? "flat" : dir > 0 ? "bull" : "bear";
  const sign = tone === "bull" ? "+" : tone === "bear" ? "−" : "";

  return (
    <Card className={cn("card-hover", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-xs font-medium text-muted-foreground">
            {name}
          </CardTitle>
          {/* 固定佔位（未給也保留一行），確保多張卡片標題列等高、數值列對齊 */}
          <span className="num text-[10px] leading-none text-muted-foreground/70">
            {subtitle ?? " "}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <p className="num text-2xl font-bold leading-tight">{fmtValue(value)}</p>
        {dir !== null ? (
          <p
            data-tone={tone}
            className={cn(
              "mt-1 flex items-center gap-1 num text-sm font-medium",
              tone === "bull" && "text-bull",
              tone === "bear" && "text-bear",
              tone === "flat" && "text-flat",
            )}
          >
            {tone === "bull" ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : tone === "bear" ? (
              <TrendingDown className="h-3.5 w-3.5" />
            ) : (
              <Minus className="h-3.5 w-3.5" />
            )}
            {/* 漲跌「點數」在前、百分比在括號內——使用者要能一眼看出漲跌多少點 */}
            {chg !== null ? (
              <span>
                {sign}
                {Math.abs(chg).toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            ) : null}
            {num !== null ? (
              <span className={cn(chg !== null && "text-[0.92em] opacity-90")}>
                {chg !== null ? "(" : ""}
                {sign}
                {Math.abs(num).toFixed(2)}%{chg !== null ? ")" : ""}
              </span>
            ) : null}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

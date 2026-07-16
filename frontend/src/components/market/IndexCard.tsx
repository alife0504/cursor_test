import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// 大盤指數卡片（紅漲綠跌）
interface IndexCardProps {
  name: string;
  value?: string | number | null;
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

export function IndexCard({
  name,
  value,
  changePct,
  subtitle,
  className,
}: IndexCardProps) {
  const num =
    changePct === null || changePct === undefined ? null : Number(changePct);
  const tone: "bull" | "bear" | "flat" =
    num === null || !Number.isFinite(num) || num === 0
      ? "flat"
      : num > 0
        ? "bull"
        : "bear";

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
        {num !== null && Number.isFinite(num) ? (
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
            {tone === "bull" ? "+" : tone === "bear" ? "−" : ""}
            {Math.abs(num).toFixed(2)}%
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

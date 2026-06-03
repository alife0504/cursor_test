import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// 大盤指數卡片（紅漲綠跌）
interface IndexCardProps {
  name: string;
  value?: string | number | null;
  changePct?: string | number | null;
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
        <CardTitle className="text-xs font-medium text-muted-foreground">
          {name}
        </CardTitle>
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

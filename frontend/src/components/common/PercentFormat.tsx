import { cn } from "@/lib/utils";
import { formatPercent, type Numeric } from "@/lib/format";

interface PercentFormatProps {
  value: Numeric | null | undefined;
  decimals?: number;
  /** 依正負加紅綠色（台股慣例：紅漲綠跌） */
  colored?: boolean;
  className?: string;
  fallback?: string;
}

export function PercentFormat({
  value,
  decimals = 2,
  colored = false,
  className,
  fallback = "—",
}: PercentFormatProps) {
  const text = formatPercent(value, decimals, fallback);
  let colorClass = "";
  let tone: "bull" | "bear" | "flat" = "flat";
  if (colored && value !== null && value !== undefined && value !== "") {
    const num = Number(value);
    if (!Number.isNaN(num)) {
      if (num > 0) {
        colorClass = "text-bull";
        tone = "bull";
      } else if (num < 0) {
        colorClass = "text-bear";
        tone = "bear";
      }
    }
  }
  return (
    <span data-tone={colored ? tone : undefined} className={cn("num", colorClass, className)}>
      {text}
    </span>
  );
}

import { cn } from "@/lib/utils";
import { formatPercent, type Numeric } from "@/lib/format";

interface PercentFormatProps {
  value: Numeric | null | undefined;
  decimals?: number;
  /** 是否依正負加紅綠色,預設關 */
  colored?: boolean;
  className?: string;
  fallback?: string;
}

export function PercentFormat({
  value,
  decimals = 2,
  colored = false,
  className,
  fallback = "-",
}: PercentFormatProps) {
  const text = formatPercent(value, decimals, fallback);
  let colorClass = "";
  if (colored && value !== null && value !== undefined && value !== "") {
    const num = Number(value);
    if (!Number.isNaN(num)) {
      if (num > 0) colorClass = "text-green-600 dark:text-green-400";
      else if (num < 0) colorClass = "text-red-600 dark:text-red-400";
    }
  }
  return (
    <span className={cn("tabular-nums", colorClass, className)}>{text}</span>
  );
}

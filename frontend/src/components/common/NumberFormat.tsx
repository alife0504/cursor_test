import { cn } from "@/lib/utils";
import { formatNumber, type Numeric } from "@/lib/format";

interface NumberFormatProps {
  value: Numeric | null | undefined;
  decimals?: number;
  className?: string;
  fallback?: string;
}

// 直接渲染金額/數字會把 Decimal 字串原樣印出,千分位用此元件統一處理
export function NumberFormat({
  value,
  decimals = 0,
  className,
  fallback = "-",
}: NumberFormatProps) {
  return (
    <span className={cn("tabular-nums", className)}>
      {formatNumber(value, decimals, fallback)}
    </span>
  );
}

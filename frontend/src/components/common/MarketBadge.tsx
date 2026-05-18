import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// P15 原版只收 TW/US;P16 擴充以容納後端 watchlist/orders 用的細分市場代碼。
export type Market =
  | "TW"
  | "US"
  | "TWSE"
  | "TPEX"
  | "NYSE"
  | "NASDAQ"
  | "AMEX"
  | "OTHER"
  | string;

interface MarketBadgeProps {
  market: Market;
  className?: string;
}

function classify(market: string): "TW" | "US" | "OTHER" {
  const m = (market || "").toUpperCase();
  if (m === "TW" || m === "TWSE" || m === "TPEX") return "TW";
  if (m === "US" || m === "NYSE" || m === "NASDAQ" || m === "AMEX") return "US";
  return "OTHER";
}

const groupStyle: Record<"TW" | "US" | "OTHER", string> = {
  TW: "bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-900/40 dark:text-emerald-100",
  US: "bg-sky-100 text-sky-900 hover:bg-sky-100 dark:bg-sky-900/40 dark:text-sky-100",
  OTHER: "bg-muted text-muted-foreground hover:bg-muted",
};

const groupLabel: Record<"TW" | "US" | "OTHER", string> = {
  TW: "🇹🇼 台股",
  US: "🇺🇸 美股",
  OTHER: "其他",
};

export function MarketBadge({ market, className }: MarketBadgeProps) {
  const group = classify(market);
  return (
    <Badge variant="secondary" className={cn(groupStyle[group], className)}>
      {groupLabel[group]}
    </Badge>
  );
}

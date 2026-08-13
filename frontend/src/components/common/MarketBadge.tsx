import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// P15 原版只收 TW/US；P16 擴充以容納後端 watchlist/orders 用的細分市場代碼。
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
  /** 是否顯示明細（TWSE / TPEX / NYSE 等），預設 false 只顯示「台股 / 美股」 */
  showDetail?: boolean;
}

function classify(market: string): "TW" | "US" | "OTHER" {
  const m = (market || "").toUpperCase();
  if (m === "TW" || m === "TWSE" || m === "TPEX") return "TW";
  if (m === "US" || m === "NYSE" || m === "NASDAQ" || m === "AMEX") return "US";
  return "OTHER";
}

const groupStyle: Record<"TW" | "US" | "OTHER", string> = {
  // 用品牌色而非用漲跌色，避免誤導
  TW: "bg-info/10 text-info ring-1 ring-info/20 hover:bg-info/10",
  US: "bg-chart-3/15 text-chart-3 ring-1 ring-chart-3/30 hover:bg-chart-3/15",
  OTHER: "bg-muted text-muted-foreground ring-1 ring-border hover:bg-muted",
};

const groupLabel: Record<"TW" | "US" | "OTHER", string> = {
  TW: "🇹🇼 台股",
  US: "🇺🇸 美股",
  OTHER: "其他",
};

export function MarketBadge({
  market,
  className,
  showDetail = false,
}: MarketBadgeProps) {
  const group = classify(market);
  const detail =
    showDetail && market && market.toUpperCase() !== group
      ? ` · ${market.toUpperCase()}`
      : "";
  return (
    <Badge
      variant="secondary"
      data-market-group={group}
      className={cn("font-medium", groupStyle[group], className)}
    >
      {groupLabel[group]}
      {detail ? (
        <span className="ml-1 text-[10px] opacity-80">{detail}</span>
      ) : null}
    </Badge>
  );
}

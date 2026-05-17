import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type Market = "TW" | "US";

interface MarketBadgeProps {
  market: Market;
  className?: string;
}

const marketStyle: Record<Market, string> = {
  TW: "bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-900/40 dark:text-emerald-100",
  US: "bg-sky-100 text-sky-900 hover:bg-sky-100 dark:bg-sky-900/40 dark:text-sky-100",
};

const marketLabel: Record<Market, string> = {
  TW: "🇹🇼 台股",
  US: "🇺🇸 美股",
};

export function MarketBadge({ market, className }: MarketBadgeProps) {
  return (
    <Badge variant="secondary" className={cn(marketStyle[market], className)}>
      {marketLabel[market]}
    </Badge>
  );
}

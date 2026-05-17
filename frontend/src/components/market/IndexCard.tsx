import { TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// Phase 17 § B:大盤指數卡片
//   - TW 加權 / 櫃買;US S&P / NASDAQ / Dow

interface IndexCardProps {
  name: string;
  value?: string | number | null;
  changePct?: string | number | null;
  className?: string;
}

export function IndexCard({ name, value, changePct, className }: IndexCardProps) {
  const num = changePct === null || changePct === undefined ? null : Number(changePct);
  const positive = num !== null && num >= 0;
  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">{name}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold tabular-nums">
          {value !== null && value !== undefined ? String(value) : "-"}
        </p>
        {num !== null && Number.isFinite(num) ? (
          <p
            className={cn(
              "mt-1 flex items-center gap-1 text-sm tabular-nums",
              positive ? "text-emerald-600" : "text-rose-600",
            )}
          >
            {positive ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5" />
            )}
            {positive ? "+" : ""}
            {num.toFixed(2)}%
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

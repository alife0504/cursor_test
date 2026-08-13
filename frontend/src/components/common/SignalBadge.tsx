import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SignalBadgeProps {
  signal?: string | null;
  status?: string | null;
  className?: string;
}

// 訊號（台股慣例：BUY=紅、SELL=綠、HOLD=橙）
const signalStyle: Record<string, { cls: string; tone: string; label: string }> =
  {
    BUY: {
      cls: "bg-signal-buy-muted text-signal-buy ring-1 ring-signal-buy/20",
      tone: "buy",
      label: "買進",
    },
    SELL: {
      cls: "bg-signal-sell-muted text-signal-sell ring-1 ring-signal-sell/20",
      tone: "sell",
      label: "賣出",
    },
    HOLD: {
      cls: "bg-signal-hold-muted text-signal-hold ring-1 ring-signal-hold/20",
      tone: "hold",
      label: "持有",
    },
  };

const statusStyle: Record<string, { cls: string; label: string }> = {
  queued: {
    cls: "bg-muted text-muted-foreground ring-1 ring-border",
    label: "排隊中",
  },
  running: {
    cls: "bg-info/10 text-info ring-1 ring-info/20 animate-pulse",
    label: "分析中",
  },
  completed: {
    cls: "bg-success/10 text-success ring-1 ring-success/20",
    label: "已完成",
  },
  failed: {
    cls: "bg-destructive/10 text-destructive ring-1 ring-destructive/20",
    label: "失敗",
  },
  cancelled: {
    cls: "bg-muted text-muted-foreground ring-1 ring-border line-through",
    label: "已取消",
  },
};

export function SignalBadge({ signal, status, className }: SignalBadgeProps) {
  // 已完成優先顯示 signal；進行中或失敗顯示 status
  if (signal && status === "completed") {
    const s = signalStyle[signal.toUpperCase()] ?? null;
    if (s) {
      return (
        <Badge
          variant="secondary"
          data-tone={s.tone}
          className={cn("font-semibold", s.cls, className)}
        >
          {s.label}（{signal.toUpperCase()}）
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className={className}>
        {signal}
      </Badge>
    );
  }
  if (status) {
    const st = statusStyle[status] ?? null;
    if (st) {
      return (
        <Badge
          variant="secondary"
          data-status={status}
          className={cn(st.cls, className)}
        >
          {st.label}
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className={className} data-status={status}>
        {status}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className={className}>
      -
    </Badge>
  );
}

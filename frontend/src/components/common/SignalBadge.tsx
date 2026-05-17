import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SignalBadgeProps {
  signal?: string | null;
  status?: string | null;
  className?: string;
}

// Phase 16:統一顯示分析訊號與狀態
//   - signal: BUY (綠) / SELL (紅) / HOLD (黃)
//   - status: queued / running / completed / failed / cancelled
const signalStyle: Record<string, string> = {
  BUY: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100",
  SELL: "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-100",
  HOLD: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100",
};

const statusStyle: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-slate-200",
  running: "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-100",
  completed: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100",
  failed: "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-100",
  cancelled: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-200",
};

const statusLabel: Record<string, string> = {
  queued: "排隊中",
  running: "分析中",
  completed: "已完成",
  failed: "失敗",
  cancelled: "已取消",
};

export function SignalBadge({ signal, status, className }: SignalBadgeProps) {
  // 已完成優先顯示 signal;進行中或失敗顯示 status
  if (signal && status === "completed") {
    return (
      <Badge variant="secondary" className={cn(signalStyle[signal] || "", className)}>
        {signal}
      </Badge>
    );
  }
  if (status) {
    return (
      <Badge variant="secondary" className={cn(statusStyle[status] || "", className)}>
        {statusLabel[status] || status}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className={className}>
      -
    </Badge>
  );
}

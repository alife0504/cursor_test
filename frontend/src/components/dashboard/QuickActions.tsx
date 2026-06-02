"use client";

import {
  Bell,
  CheckSquare,
  PenSquare,
  Star,
  type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";

import { cn } from "@/lib/utils";

interface ActionItem {
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
  accent: "primary" | "warning" | "info" | "bull";
}

const ACTIONS: ActionItem[] = [
  {
    label: "新增分析",
    description: "選股 → analyst → 模型 → 送出",
    href: "/analysis/new",
    icon: PenSquare,
    accent: "primary",
  },
  {
    label: "加入自選股",
    description: "管理你關注的股票",
    href: "/screener/watchlist",
    icon: Star,
    accent: "info",
  },
  {
    label: "看待核准訂單",
    description: "AI 訊號自動產生 PENDING",
    href: "/portfolio/orders",
    icon: CheckSquare,
    accent: "warning",
  },
  {
    label: "通知設定",
    description: "LINE / Telegram 設定",
    href: "/notifications",
    icon: Bell,
    accent: "bull",
  },
];

const ACCENT: Record<ActionItem["accent"], string> = {
  primary: "bg-primary/10 text-primary group-hover:bg-primary/15",
  warning: "bg-warning/10 text-warning group-hover:bg-warning/15",
  info: "bg-info/10 text-info group-hover:bg-info/15",
  bull: "bg-bull-muted text-bull group-hover:bg-bull-muted/80",
};

export function QuickActions() {
  const router = useRouter();
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {ACTIONS.map((a) => {
        const Icon = a.icon;
        return (
          <button
            key={a.href}
            type="button"
            onClick={() => router.push(a.href)}
            className={cn(
              "group flex items-center gap-3 rounded-lg border bg-card p-3 text-left transition-all card-hover",
            )}
          >
            <span
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-md transition-colors",
                ACCENT[a.accent],
              )}
            >
              <Icon className="h-5 w-5" />
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="text-sm font-medium">{a.label}</span>
              <span className="truncate text-xs text-muted-foreground">
                {a.description}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

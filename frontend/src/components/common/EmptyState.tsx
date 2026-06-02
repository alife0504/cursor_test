import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title?: ReactNode;
  description?: ReactNode;
  action?: { label: string; onClick: () => void };
  /** 次要動作（通常 ghost variant） */
  secondaryAction?: { label: string; onClick: () => void };
  /** "card"：完整置中卡片（預設）；"inline"：精簡 inline 樣式（widget 用） */
  variant?: "card" | "inline";
  className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title = "目前沒有資料",
  description,
  action,
  secondaryAction,
  variant = "card",
  className,
}: EmptyStateProps) {
  if (variant === "inline") {
    return (
      <div
        className={cn(
          "flex w-full items-center gap-3 rounded-md border border-dashed bg-muted/30 px-3 py-3 text-sm",
          className,
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="truncate font-medium">{title}</p>
          {description ? (
            <p className="truncate text-xs text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {action ? (
          <Button variant="outline" size="sm" onClick={action.onClick}>
            {action.label}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex w-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/30 px-6 py-12 text-center animate-fade-in",
        className,
      )}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-background text-muted-foreground shadow-soft ring-1 ring-border">
        <Icon className="h-7 w-7" />
      </div>
      <div className="space-y-1 max-w-md">
        <p className="font-semibold">{title}</p>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {(action || secondaryAction) && (
        <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
          {action ? (
            <Button size="sm" onClick={action.onClick}>
              {action.label}
            </Button>
          ) : null}
          {secondaryAction ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={secondaryAction.onClick}
            >
              {secondaryAction.label}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
}

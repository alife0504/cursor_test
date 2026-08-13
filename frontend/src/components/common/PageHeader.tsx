import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * 統一頁首：標題 + 副標 + 右側 action slot。
 * 取代每頁手刻的 `<h1> + <p>` 重複碼。
 *
 * icon：頁面主題 icon（與側欄導覽同一顆），以品牌漸層 chip 呈現，
 * 給每頁一個視覺錨點、強化「我在哪」的辨識。
 */
interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** 副標下方可插入 meta（如資料日期、市場切換） */
  meta?: ReactNode;
  /** 頁面主題 icon（漸層 chip） */
  icon?: LucideIcon;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  meta,
  icon: Icon,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-start sm:justify-between sm:gap-4",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        {Icon ? (
          <div className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-primary to-chart-3 text-primary-foreground shadow-lift">
            <Icon className="h-5 w-5" />
          </div>
        ) : null}
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight md:text-[26px]">
            {title}
          </h1>
          {description ? (
            <p className="text-sm text-muted-foreground">{description}</p>
          ) : null}
          {meta ? <div className="pt-1">{meta}</div> : null}
        </div>
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
          {actions}
        </div>
      ) : null}
    </header>
  );
}

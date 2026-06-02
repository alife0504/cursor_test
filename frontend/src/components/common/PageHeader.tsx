import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * 統一頁首：標題 + 副標 + 右側 action slot。
 * 取代每頁手刻的 `<h1> + <p>` 重複碼。
 */
interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** 副標下方可插入 meta（如資料日期、市場切換） */
  meta?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-start sm:justify-between sm:gap-4",
        className,
      )}
    >
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight md:text-[26px]">
          {title}
        </h1>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
        {meta ? <div className="pt-1">{meta}</div> : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
          {actions}
        </div>
      ) : null}
    </header>
  );
}

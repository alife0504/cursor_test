import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";

// Phase 17:mock 頁面警示橫幅
//   - 為 calendar / compare / backtest 等 v1.1 才會接後端的頁面
//   - 必須含「Mock」+「v1.1」字串(供 health_check grep)

export interface MockBannerProps {
  title?: string;
  className?: string;
  /** v1.1 的對應 ticket id / runbook 連結;非必填 */
  trackingRef?: string;
}

export function MockBanner({
  title = "本頁顯示 Mock 資料 - v1.1 將完整實作",
  className,
  trackingRef,
}: MockBannerProps) {
  return (
    <div
      data-testid="mock-banner"
      className={cn(
        "flex items-start gap-3 rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
      <div className="flex flex-col gap-1">
        <p className="font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">
          頁面結構與 v1.1 對齊,後端對應 endpoint 完成後可直接接上。
          {trackingRef ? ` 追蹤:${trackingRef}` : null}
        </p>
      </div>
    </div>
  );
}

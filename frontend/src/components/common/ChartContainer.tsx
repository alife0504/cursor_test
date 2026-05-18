import { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface ChartContainerProps {
  children: ReactNode;
  /** 固定高度避免 lightweight-charts / recharts 計算 0 */
  height?: number | string;
  className?: string;
  title?: ReactNode;
  toolbar?: ReactNode;
}

// PLAN § R 已知陷阱:lightweight-charts 在父層沒高度時會 silently 渲染 0px,
// 用此 wrapper 強制給 height
export function ChartContainer({
  children,
  height = 360,
  className,
  title,
  toolbar,
}: ChartContainerProps) {
  return (
    <div
      className={cn(
        "flex w-full flex-col gap-2 rounded-lg border bg-card p-3",
        className,
      )}
    >
      {(title || toolbar) && (
        <div className="flex items-center justify-between">
          {title && <h3 className="text-sm font-medium">{title}</h3>}
          {toolbar}
        </div>
      )}
      <div
        className="relative w-full overflow-hidden"
        style={{
          height: typeof height === "number" ? `${height}px` : height,
        }}
      >
        {children}
      </div>
    </div>
  );
}

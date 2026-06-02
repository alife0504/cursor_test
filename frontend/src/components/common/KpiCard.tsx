"use client";

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { PriceDelta } from "@/components/common/PriceDelta";
import { Sparkline } from "@/components/common/Sparkline";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * 儀表板 / 概覽頁通用 KPI 卡。
 *
 * 結構：
 *   icon  | title (subtle)
 *   value (大字 tabular-nums)
 *   delta (PriceDelta) ・ subtitle/sparkline 區
 *
 * tone：強制指定漲跌色（不傳時由 PriceDelta 自動判讀）。
 */
interface KpiCardProps {
  title: ReactNode;
  /** 主數值（已格式化文字 / 或 number / 或自定 ReactNode） */
  value: ReactNode;
  /** 漲跌幅或變化值（用 PriceDelta 顯示） */
  delta?: number | string | null;
  deltaMode?: "pct" | "raw" | "abs" | "both";
  deltaSuffix?: string;
  /** sparkline 數列 */
  spark?: Array<number | string | null | undefined>;
  /** 強制 tone */
  tone?: "bull" | "bear" | "flat";
  /** 左上角 icon */
  icon?: LucideIcon;
  /** subtitle 在 value 下面、與 delta 並排（短說明文字） */
  subtitle?: ReactNode;
  /** 點擊整張卡（會加 hover 提示） */
  onClick?: () => void;
  /** 右下角自訂 slot（如「前往 →」連結） */
  footer?: ReactNode;
  className?: string;
  /** 強調色（運算後配色，預設無；常用：bull / bear / warning） */
  accent?: "bull" | "bear" | "warning" | "info" | "primary";
}

export function KpiCard({
  title,
  value,
  delta,
  deltaMode = "raw",
  deltaSuffix,
  spark,
  tone,
  icon: Icon,
  subtitle,
  onClick,
  footer,
  className,
  accent,
}: KpiCardProps) {
  const accentBar =
    accent === "bull"
      ? "bg-bull"
      : accent === "bear"
        ? "bg-bear"
        : accent === "warning"
          ? "bg-warning"
          : accent === "info"
            ? "bg-info"
            : accent === "primary"
              ? "bg-primary"
              : "bg-transparent";

  const interactive = !!onClick;

  return (
    <Card
      onClick={onClick}
      className={cn(
        "relative overflow-hidden card-hover",
        interactive && "cursor-pointer",
        className,
      )}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
    >
      {/* 左側強調色條 */}
      <div
        aria-hidden
        className={cn("absolute inset-y-0 left-0 w-1", accentBar)}
      />
      <CardContent className="flex flex-col gap-2 p-4 pl-5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
            <span className="truncate">{title}</span>
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="num text-2xl font-bold leading-tight">{value}</span>
          {delta !== undefined && delta !== null ? (
            <PriceDelta
              value={delta}
              mode={deltaMode}
              suffix={deltaSuffix}
              showIcon
              className="text-xs"
            />
          ) : null}
        </div>
        {(subtitle || (spark && spark.length > 1)) && (
          <div className="flex items-center justify-between gap-3">
            {subtitle ? (
              <span className="text-xs text-muted-foreground">{subtitle}</span>
            ) : (
              <span />
            )}
            {spark && spark.length > 1 ? (
              <div className="flex-1 max-w-[120px]">
                <Sparkline data={spark} tone={tone} height={32} />
              </div>
            ) : null}
          </div>
        )}
        {footer ? (
          <div className="border-t pt-2 text-xs text-muted-foreground">
            {footer}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

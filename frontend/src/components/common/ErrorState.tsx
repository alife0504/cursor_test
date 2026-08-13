"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { Illustration } from "@/components/common/Illustration";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * 統一錯誤態。取代到處 `<p className="text-destructive">無法載入...</p>`。
 *
 * 行為：
 * - 顯示 icon + 標題 + （可選）副標
 * - 若提供 onRetry，附「重試」按鈕
 * - error.message 可選顯示為 detail（給 dev 看；prod 預設隱藏）
 */
interface ErrorStateProps {
  title?: ReactNode;
  description?: ReactNode;
  /** 重試 callback；提供時顯示按鈕 */
  onRetry?: () => void;
  retryLabel?: string;
  /** Error 物件或 detail string；預設 dev 顯示、prod 隱藏 */
  error?: unknown;
  showDetail?: boolean;
  /** "inline"：精簡橫排（給 widget 用），"card"：完整置中卡片 */
  variant?: "inline" | "card";
  className?: string;
}

function getMessage(err: unknown): string | null {
  if (!err) return null;
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message;
  if (typeof err === "object" && err !== null && "message" in err) {
    const m = (err as { message: unknown }).message;
    if (typeof m === "string") return m;
  }
  return null;
}

export function ErrorState({
  title = "載入失敗",
  description,
  onRetry,
  retryLabel = "重試",
  error,
  showDetail,
  variant = "card",
  className,
}: ErrorStateProps) {
  const detail =
    showDetail ?? process.env.NODE_ENV !== "production" ? getMessage(error) : null;

  if (variant === "inline") {
    return (
      <div
        role="alert"
        className={cn(
          "flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          <div className="space-y-0.5">
            <p className="font-medium text-destructive">{title}</p>
            {description ? (
              <p className="text-xs text-muted-foreground">{description}</p>
            ) : null}
            {detail ? (
              <p className="break-all text-[10px] text-muted-foreground/70">
                {detail}
              </p>
            ) : null}
          </div>
        </div>
        {onRetry ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="shrink-0"
          >
            <RefreshCw className="mr-1 h-3 w-3" /> {retryLabel}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={cn(
        "flex w-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-destructive/30 bg-destructive/5 py-10 text-center",
        className,
      )}
    >
      <Illustration name="error" className="h-24" />
      <div className="space-y-1">
        <p className="font-semibold">{title}</p>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
        {detail ? (
          <p className="break-all px-4 text-xs text-muted-foreground/70">
            {detail}
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-1 h-3 w-3" /> {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}

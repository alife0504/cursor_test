"use client";

import { Check, Circle, Loader2, X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * 分析詳情頁進度視覺化（5 階段）：
 *   Queue → Analysts → Debate → Manager → Done
 *
 * 狀態映射規則：
 *   - queued    → step 1 active
 *   - running 且 debate 尚未開始 → step 2 active
 *   - running 且有 debate msgs → step 3 active
 *   - running 且 manager 已產 final → step 4 active
 *   - completed → 全綠勾
 *   - failed    → 當前 step 紅 X
 *   - cancelled → 灰色不再動
 */
export type AnalysisStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | string;

interface StatusStepperProps {
  status: AnalysisStatus;
  debateCount?: number;
  /** Manager 是否已完成（管理員給 signal） */
  managerDone?: boolean;
  className?: string;
}

const STEPS = [
  { key: "queued", label: "排隊中" },
  { key: "analysts", label: "Analyst 分析" },
  { key: "debate", label: "多空辯論" },
  { key: "manager", label: "Manager 綜合" },
  { key: "done", label: "完成" },
] as const;

function deriveActiveIndex(
  status: AnalysisStatus,
  debateCount: number,
  managerDone: boolean,
): number {
  if (status === "completed") return 4;
  if (status === "failed" || status === "cancelled") {
    // 推斷停在哪一階段
    if (managerDone) return 3;
    if (debateCount > 0) return 2;
    return 1;
  }
  if (status === "queued") return 0;
  // running
  if (managerDone) return 3;
  if (debateCount > 0) return 2;
  return 1;
}

export function StatusStepper({
  status,
  debateCount = 0,
  managerDone = false,
  className,
}: StatusStepperProps) {
  const activeIdx = deriveActiveIndex(status, debateCount, managerDone);
  const isFailed = status === "failed" || status === "cancelled";
  const isDone = status === "completed";

  return (
    <ol
      aria-label="分析進度"
      className={cn(
        "flex w-full flex-wrap items-center gap-y-3 rounded-lg border bg-card p-3 sm:flex-nowrap sm:gap-y-0",
        className,
      )}
    >
      {STEPS.map((s, i) => {
        const isPast = i < activeIdx;
        const isCurrent = i === activeIdx && !isDone;
        const isFuture = i > activeIdx;
        const colorRing =
          isCurrent && isFailed
            ? "bg-state-failed-muted border-state-failed text-state-failed"
            : isCurrent
              ? "bg-state-running-muted border-state-running text-state-running animate-pulse-glow"
              : isPast || isDone
                ? "bg-state-done-muted border-state-done text-state-done"
                : "bg-muted border-state-pending text-state-pending";

        return (
          <li
            key={s.key}
            className="flex flex-1 items-center gap-2 min-w-[140px]"
            aria-current={isCurrent ? "step" : undefined}
            data-state={
              isCurrent
                ? isFailed
                  ? "failed"
                  : "running"
                : isPast || isDone
                  ? "done"
                  : "pending"
            }
          >
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2",
                colorRing,
              )}
            >
              {isCurrent && isFailed ? (
                <X className="h-3.5 w-3.5" />
              ) : isCurrent && !isFailed ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : isPast || isDone ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <Circle className="h-3.5 w-3.5" />
              )}
            </div>
            <div className="flex flex-col">
              <span
                className={cn(
                  "text-xs font-medium",
                  isFuture ? "text-muted-foreground" : "text-foreground",
                )}
              >
                {s.label}
              </span>
              <span className="text-[10px] text-muted-foreground">
                Step {i + 1}/{STEPS.length}
              </span>
            </div>
            {i < STEPS.length - 1 ? (
              <span
                aria-hidden
                className={cn(
                  "hidden flex-1 border-t-2 sm:block",
                  isPast || (isCurrent && isDone)
                    ? "border-state-done"
                    : "border-dashed border-state-pending/50",
                )}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

"use client";

import { AlertTriangle, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useDataFreshness } from "@/hooks/useSystem";
import { cn } from "@/lib/utils";

// 委託人收尾第一重點：「發現異常，網頁要顯示警示」。
//   - 掛在 (app)/layout 主內容區頂端，所有登入後頁面共用。
//   - 僅在整體 status 為 warn（黃）/ critical（紅）時顯示；ok / unknown / 載入中 / 端點失敗
//     一律不顯示（此端點掛掉絕不可擋住頁面）。
//   - 可關閉：關閉狀態記到 sessionStorage（當次瀏覽期有效）；以「狀態+異常摘要」為簽章，
//     異常內容一旦變化（例如新表過期、或升級為 critical）會重新顯示，不會被舊的關閉狀態蓋掉。

const DISMISS_KEY = "system-health-banner-dismissed";

export function SystemHealthBanner() {
  // 端點失敗時 data 為 undefined → 下方 early return null，不影響頁面。
  const { data } = useDataFreshness();

  // sessionStorage 只能在 client 讀（避免 SSR / hydration 不一致）。
  const [dismissedSig, setDismissedSig] = useState<string | null>(null);
  useEffect(() => {
    try {
      setDismissedSig(sessionStorage.getItem(DISMISS_KEY));
    } catch {
      // sessionStorage 不可用（隱私模式 / 被封鎖）→ 視為未關閉，仍能顯示警示。
    }
  }, []);

  const status = data?.status;
  // 只有 warn / critical 才顯示；其餘（含載入中、錯誤、正常）不顯示。
  if (status !== "warn" && status !== "critical") return null;

  // 簽章：狀態或異常摘要一改變就重新示警（不沿用舊的關閉狀態）。
  const signature = `${status}:${data?.problem_summary ?? ""}`;
  if (dismissedSig === signature) return null;

  const isCritical = status === "critical";

  const dismiss = () => {
    try {
      sessionStorage.setItem(DISMISS_KEY, signature);
    } catch {
      // 無法寫入時仍以記憶體狀態關閉（當次 render 生效）。
    }
    setDismissedSig(signature);
  };

  return (
    <div
      role="alert"
      data-testid="system-health-banner"
      className={cn(
        "flex items-start gap-3 rounded-lg border p-3 text-sm",
        isCritical
          ? "border-destructive/40 bg-destructive/10"
          : "border-warning/40 bg-warning/10",
      )}
    >
      <AlertTriangle
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          isCritical ? "text-destructive" : "text-warning",
        )}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="font-medium">
          資料更新異常
          {data?.problem_summary ? `：${data.problem_summary}` : ""}
        </p>
        <p className="text-xs text-muted-foreground">
          部分資料可能不是最新，請留意判讀；點右側可查看資料管線詳情。
        </p>
      </div>
      <Link
        href="/admin/pipeline"
        className="mt-0.5 shrink-0 whitespace-nowrap text-xs font-medium underline underline-offset-2 hover:opacity-80"
      >
        查看詳情
      </Link>
      <button
        type="button"
        onClick={dismiss}
        aria-label="關閉警示"
        className="-mt-0.5 -mr-1 shrink-0 rounded p-1 text-muted-foreground transition-colors hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

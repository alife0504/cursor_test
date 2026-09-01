"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/common/ErrorState";

// (app) 群組的 segment 錯誤邊界：頁面 render 出錯時，於 app 版型（側欄 / Topbar 仍在）
// 內顯示友善錯誤卡 + 重試，不讓整個應用白屏。reset() 會重新嘗試 render 該頁。
export default function AppSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[app/error]", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] w-full items-center justify-center">
      <ErrorState
        title="這個頁面發生錯誤"
        description="可以重試載入，或稍後再試；其他功能不受影響。"
        onRetry={reset}
        error={error}
        className="max-w-lg"
      />
    </div>
  );
}

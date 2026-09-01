"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/common/ErrorState";

// onboarding 群組的 segment 錯誤邊界（如首次登入強制改密碼頁）。render 出錯時顯示
// 友善錯誤卡 + 重試，不讓 onboarding 流程白屏卡死。
export default function OnboardingSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[onboarding/error]", error);
  }, [error]);

  return (
    <ErrorState
      title="頁面載入失敗"
      description="請點重試重新載入；若持續發生請稍後再試。"
      onRetry={reset}
      error={error}
    />
  );
}

"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/common/ErrorState";

// (auth) 群組的 segment 錯誤邊界。登入 / 忘記密碼 / 重設密碼頁 render 出錯時，
// 於品牌版型的表單卡位置顯示友善錯誤卡 + 重試——尤其重要：登入頁掛掉不能讓使用者
// 完全無法登入，至少給「重試」回到可用狀態。
export default function AuthSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[auth/error]", error);
  }, [error]);

  return (
    <ErrorState
      title="登入頁載入失敗"
      description="請點重試重新載入登入畫面；若持續發生請稍後再試。"
      onRetry={reset}
      error={error}
    />
  );
}

"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ErrorBoundary } from "@/components/common/ErrorBoundary";

/**
 * 以當前路徑當 key 包住 ErrorBoundary：導頁時 pathname 改變 → key 改變 →
 * ErrorBoundary 整個重新掛載，清掉上一頁殘留的錯誤狀態。
 *
 * 修正「A 頁 render 出錯後切到 B 頁，仍卡在錯誤卡」的問題——ErrorBoundary 是 class
 * component 且只有 getDerivedStateFromError + 手動 reset()，本身不會隨路由自動重置。
 *
 * layout 為 server component，usePathname 僅能在 client 用，故抽成此 client 小包裝，
 * 不破壞既有 server/client 邊界。
 */
export function RouteResetErrorBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return <ErrorBoundary key={pathname}>{children}</ErrorBoundary>;
}

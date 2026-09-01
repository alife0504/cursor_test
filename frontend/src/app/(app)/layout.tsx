import { AuthBootstrap } from "@/components/common/AuthBootstrap";
import { CommandPalette } from "@/components/common/CommandPalette";
import { RouteResetErrorBoundary } from "@/components/common/RouteResetErrorBoundary";
import { MobileSidebar, Sidebar } from "@/components/common/Sidebar";
import { SystemHealthBanner } from "@/components/common/SystemHealthBanner";
import { Topbar } from "@/components/common/Topbar";

// 已登入 App 主版型：Sidebar（桌機）+ MobileSidebar（手機 Sheet）+ Topbar + main
//  - Breadcrumbs：已內嵌於 Topbar 左側（桌機），內容區不再另佔一行
//  - CommandPalette：全域 ⌘K
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full">
      <Sidebar />
      <MobileSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto bg-app-mesh">
          <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 p-4 sm:p-6 lg:px-8">
            {/* 全站資料異常警示：置於內容最上方、錯誤邊界之外，頁面出錯時仍看得到 */}
            <SystemHealthBanner />
            {/* key={pathname} 讓導頁時錯誤邊界重置，避免單頁錯誤黏住全站 */}
            <RouteResetErrorBoundary>
              <AuthBootstrap />
              {children}
            </RouteResetErrorBoundary>
          </div>
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

import { AuthBootstrap } from "@/components/common/AuthBootstrap";
import { Breadcrumbs } from "@/components/common/Breadcrumbs";
import { CommandPalette } from "@/components/common/CommandPalette";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { MobileSidebar, Sidebar } from "@/components/common/Sidebar";
import { Topbar } from "@/components/common/Topbar";

// 已登入 App 主版型：Sidebar（桌機）+ MobileSidebar（手機 Sheet）+ Topbar + main
//  - Breadcrumbs：除 dashboard 自動顯示麵包屑
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
        <main className="flex-1 overflow-y-auto bg-muted/20">
          <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 p-4 sm:p-6">
            <Breadcrumbs />
            <ErrorBoundary>
              <AuthBootstrap />
              {children}
            </ErrorBoundary>
          </div>
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

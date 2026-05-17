import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { Sidebar } from "@/components/common/Sidebar";
import { Topbar } from "@/components/common/Topbar";
import { AuthBootstrap } from "@/components/common/AuthBootstrap";

// 已登入 App 主版型:Sidebar + Topbar + main
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">
          <ErrorBoundary>
            <AuthBootstrap />
            {children}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

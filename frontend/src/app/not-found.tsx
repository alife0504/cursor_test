import { Compass } from "lucide-react";
import Link from "next/link";

// 全域 404 頁（root not-found）：找不到路由時顯示友善提示 + 回首頁。
// 於 root layout 內 render（含 globals.css / ThemeProvider），深淺色皆正常。
export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center text-foreground">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Compass className="h-7 w-7" />
      </div>
      <div className="space-y-1">
        <p className="text-4xl font-bold tracking-tight">404</p>
        <h1 className="text-lg font-semibold">找不到這個頁面</h1>
        <p className="text-sm text-muted-foreground">
          網址可能已變更或不存在，回首頁重新開始吧。
        </p>
      </div>
      <Link
        href="/"
        className="inline-flex h-9 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        回首頁
      </Link>
    </div>
  );
}

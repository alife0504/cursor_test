"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

// globals.css 在此重新引入：global-error 會**取代 root layout**（連同其 <html><body> 與
// 樣式引入一併被換掉），故必須自帶完整文件骨架與樣式，否則會白屏 / 無樣式。
import "./globals.css";

// 最外層災難級錯誤邊界（連 root layout 都 render 失敗時才會觸發）。
//   - 必含 <html><body>：它取代 root layout。
//   - 無 ThemeProvider，以 background/foreground token 保證可讀（不白屏）。
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[global-error]", error);
  }, [error]);

  return (
    <html lang="zh-TW">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="h-7 w-7 text-destructive" />
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-bold tracking-tight">系統發生未預期的錯誤</h1>
            <p className="text-sm text-muted-foreground">
              頁面暫時無法顯示，請重新載入；若持續發生請稍後再試。
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
            <button
              type="button"
              onClick={reset}
              className="inline-flex h-9 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              重新載入
            </button>
            <a
              href="/"
              className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted"
            >
              回首頁
            </a>
          </div>
          {error?.digest ? (
            <p className="text-[11px] text-muted-foreground/70">
              錯誤代碼：{error.digest}
            </p>
          ) : null}
        </div>
      </body>
    </html>
  );
}

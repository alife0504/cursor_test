import { CandlestickChart } from "lucide-react";

import { t } from "@/i18n/messages";

// Auth 系列頁面通用 layout:置中卡片風格
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4 py-12">
      <div className="mb-6 flex flex-col items-center gap-2">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <CandlestickChart className="h-6 w-6" />
        </div>
        <div className="text-center">
          <h1 className="text-xl font-bold tracking-tight">
            {t("app.title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("app.tagline")}</p>
        </div>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}

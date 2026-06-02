"use client";

import {
  CandlestickChart,
  LogOut,
  Menu,
  Moon,
  Search,
  Sun,
  User,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { NotificationBell } from "@/components/common/NotificationBell";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { t } from "@/i18n/messages";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useUiStore } from "@/store/ui";

export function Topbar() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logoutStore = useAuthStore((s) => s.logout);
  const setMobileNavOpen = useUiStore((s) => s.setMobileNavOpen);
  const toggleCommand = useUiStore((s) => s.toggleCommand);
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const onLogout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // 即使 backend 不可用,也要清前端狀態
    } finally {
      logoutStore();
      router.replace("/login");
    }
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const initial = user?.email?.[0]?.toUpperCase() ?? "?";
  const platformMod =
    mounted && typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)
      ? "⌘"
      : "Ctrl";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-2 border-b bg-background/95 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:px-4">
      <div className="flex items-center gap-2">
        {/* Mobile 漢堡 */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileNavOpen(true)}
          aria-label="開啟選單"
          className="md:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>
        {/* Mobile 顯示品牌 */}
        <div className="flex items-center gap-2 md:hidden">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <CandlestickChart className="h-3.5 w-3.5" />
          </div>
          <span className="font-semibold text-sm tracking-tight">
            TradingAgents
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5 md:gap-2">
        {/* ⌘K 快捷觸發 */}
        <button
          type="button"
          onClick={() => toggleCommand()}
          aria-label="開啟全域搜尋"
          className="hidden h-8 items-center gap-2 rounded-md border bg-muted/40 px-3 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:inline-flex"
        >
          <Search className="h-3.5 w-3.5" />
          <span>搜尋股票、頁面、分析...</span>
          <kbd className="ml-2 rounded border bg-background px-1.5 py-0.5 text-[10px] font-mono font-medium">
            {platformMod}K
          </kbd>
        </button>
        {/* Mobile：⌘K icon-only */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => toggleCommand()}
          aria-label="開啟全域搜尋"
          className="md:hidden"
        >
          <Search className="h-4 w-4" />
        </Button>

        {/* 通知 bell */}
        <NotificationBell />

        {/* 主題切換 */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={t("topbar.theme.toggle")}
        >
          {mounted && theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>

        {/* 帳號 */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" className="flex items-center gap-2 pl-1 pr-2" />
            }
          >
            <Avatar className="h-7 w-7 ring-1 ring-border">
              <AvatarFallback className="text-xs font-medium">
                {initial}
              </AvatarFallback>
            </Avatar>
            <span className="hidden text-sm md:inline">
              {user?.email ?? t("topbar.account")}
            </span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuGroup>
              <DropdownMenuLabel>
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium">{user?.email ?? "-"}</span>
                  <span className="text-xs text-muted-foreground">
                    身分：{user?.role ?? "—"}
                  </span>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/notifications")}>
              <User className="mr-2 h-4 w-4" />
              通知設定
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={onLogout}
              className="text-destructive focus:text-destructive"
            >
              <LogOut className="mr-2 h-4 w-4" />
              {t("topbar.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

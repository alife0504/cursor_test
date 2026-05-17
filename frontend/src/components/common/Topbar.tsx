"use client";

import { LogOut, Moon, Sun, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

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

export function Topbar() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logoutStore = useAuthStore((s) => s.logout);
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

  return (
    <header className="flex h-14 items-center justify-end gap-2 border-b bg-background px-4">
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
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" className="flex items-center gap-2" />
          }
        >
          <Avatar className="h-7 w-7">
            <AvatarFallback>{initial}</AvatarFallback>
          </Avatar>
          <span className="hidden text-sm md:inline">
            {user?.email ?? t("topbar.account")}
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span className="text-xs text-muted-foreground">
                  {user?.role}
                </span>
                <span>{user?.email ?? "-"}</span>
              </div>
            </DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/notifications")}>
            <User className="mr-2 h-4 w-4" />
            通知設定
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            {t("topbar.logout")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

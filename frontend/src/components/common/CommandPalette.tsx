"use client";

import {
  Activity,
  Bell,
  Briefcase,
  Cog,
  FileSearch,
  History,
  LayoutDashboard,
  LineChart,
  Newspaper,
  PenSquare,
  Search,
  Star,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useAnalysisList } from "@/hooks/useAnalysis";
import { useStocks } from "@/hooks/useStocks";
import { useAuthStore } from "@/store/auth";
import { useUiStore } from "@/store/ui";

/**
 * 全域 ⌘K Command Palette。
 *
 * 三組：
 * 1. 股票搜尋（debounce 200ms 對 /stocks?q=）
 * 2. 頁面跳轉（18 頁 + admin filter）
 * 3. 最近分析（5 筆）
 *
 * 規則：input 有字 → 顯示股票；空字 → 顯示頁面 + 最近分析。
 * 快捷鍵：Cmd/Ctrl+K 開關；Esc 關閉；Enter 執行。
 */
const PAGES: Array<{
  href: string;
  label: string;
  keywords: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
}> = [
  { href: "/dashboard", label: "儀表板", keywords: "dashboard home", icon: LayoutDashboard },
  { href: "/market/overview", label: "市場總覽", keywords: "market overview index", icon: TrendingUp },
  { href: "/market/institutional", label: "三大法人", keywords: "institutional foreign trust dealer", icon: TrendingUp },
  { href: "/market/calendar", label: "財報日曆", keywords: "calendar earnings", icon: TrendingUp },
  { href: "/screener/watchlist", label: "自選股清單", keywords: "watchlist favorite star", icon: Star },
  { href: "/screener/filter", label: "選股篩選", keywords: "screener filter", icon: FileSearch },
  { href: "/screener/compare", label: "多股比較", keywords: "compare", icon: FileSearch },
  { href: "/analysis/new", label: "新增分析", keywords: "new analysis create", icon: PenSquare },
  { href: "/analysis/history", label: "分析歷史", keywords: "history analysis", icon: History },
  { href: "/statistics/accuracy", label: "準確率分析", keywords: "accuracy statistics", icon: LineChart },
  { href: "/statistics/models", label: "模型比較", keywords: "models comparison", icon: LineChart },
  { href: "/statistics/backtest", label: "回測結果", keywords: "backtest", icon: LineChart },
  { href: "/portfolio/positions", label: "模擬持倉", keywords: "positions portfolio", icon: Briefcase },
  { href: "/portfolio/orders", label: "待核准訂單", keywords: "orders pending approve", icon: Briefcase },
  { href: "/portfolio/history", label: "交易記錄", keywords: "history orders", icon: Briefcase },
  { href: "/news/sentiment", label: "新聞情緒", keywords: "news sentiment", icon: Newspaper },
  { href: "/news/announcements", label: "重大公告", keywords: "announcements", icon: Newspaper },
  { href: "/notifications", label: "通知設定", keywords: "notifications line telegram", icon: Bell },
  { href: "/admin/users", label: "用戶管理", keywords: "admin users", icon: Cog, adminOnly: true },
  { href: "/admin/audit", label: "審計日誌", keywords: "admin audit", icon: Cog, adminOnly: true },
  { href: "/admin/system", label: "系統監控", keywords: "admin system metrics", icon: Cog, adminOnly: true },
  { href: "/admin/pipeline", label: "資料管線", keywords: "admin pipeline dlq", icon: Cog, adminOnly: true },
];

function useDebounced<T>(value: T, ms = 200): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export function CommandPalette() {
  const router = useRouter();
  const open = useUiStore((s) => s.commandOpen);
  const setOpen = useUiStore((s) => s.setCommandOpen);
  const toggle = useUiStore((s) => s.toggleCommand);
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "ADMIN";

  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounced(query, 200);
  const hasQuery = debouncedQuery.trim().length > 0;

  // 全域快捷鍵 Cmd/Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggle]);

  // 關閉時清空 input
  useEffect(() => {
    if (!open) {
      const t = setTimeout(() => setQuery(""), 200);
      return () => clearTimeout(t);
    }
  }, [open]);

  // 股票搜尋（有 query 才 fetch）
  const { data: stocks } = useStocks(
    { q: debouncedQuery, limit: 8 },
    open && hasQuery,
  );
  const stockItems = stocks?.items ?? [];

  // 最近分析（無 query 才顯）
  const { data: recents } = useAnalysisList(
    { limit: 5 },
    open && !hasQuery,
  );
  const recentItems = recents?.items ?? [];

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="全域搜尋與導覽"
      description="搜尋股票、跳轉頁面，或回到最近分析"
    >
      <CommandInput
        placeholder="輸入股票代號 / 名稱 / 頁面..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {hasQuery ? "找不到符合的項目" : "輸入關鍵字搜尋"}
        </CommandEmpty>

        {hasQuery && stockItems.length > 0 ? (
          <CommandGroup heading="股票搜尋">
            {stockItems.map((s) => (
              <CommandItem
                key={`${s.market}:${s.symbol}`}
                value={`${s.symbol} ${s.name}`}
                onSelect={() =>
                  go(`/analysis/new?symbol=${encodeURIComponent(s.symbol)}`)
                }
              >
                <Search className="h-4 w-4 text-muted-foreground" />
                <div className="flex flex-1 items-center gap-2">
                  <span className="font-mono font-medium">{s.symbol}</span>
                  <span className="truncate text-muted-foreground">{s.name}</span>
                </div>
                <span className="text-[10px] text-muted-foreground">
                  {s.market}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {!hasQuery && recentItems.length > 0 ? (
          <CommandGroup heading="最近分析">
            {recentItems.map((a) => (
              <CommandItem
                key={a.id}
                value={`分析 ${a.symbol}`}
                onSelect={() => go(`/analysis/${a.id}`)}
              >
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="font-mono font-medium">{a.symbol}</span>
                <span className="text-xs text-muted-foreground">
                  · {a.status}
                </span>
                {a.signal ? (
                  <span className="ml-auto text-xs uppercase text-muted-foreground">
                    {a.signal}
                  </span>
                ) : null}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {(hasQuery && stockItems.length > 0) ||
        (!hasQuery && recentItems.length > 0) ? (
          <CommandSeparator />
        ) : null}

        <CommandGroup heading="頁面跳轉">
          {PAGES.filter((p) => !p.adminOnly || isAdmin).map((p) => {
            const Icon = p.icon;
            return (
              <CommandItem
                key={p.href}
                value={`${p.label} ${p.keywords}`}
                onSelect={() => go(p.href)}
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span>{p.label}</span>
                <span className="ml-auto text-[10px] font-mono text-muted-foreground">
                  {p.href}
                </span>
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

"use client";

import {
  Activity,
  BarChart3,
  Bell,
  Briefcase,
  CalendarDays,
  CandlestickChart,
  ChevronDown,
  Cog,
  Database,
  FileSearch,
  Filter,
  GitCompareArrows,
  History,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Megaphone,
  Newspaper,
  PenSquare,
  PieChart,
  ScrollText,
  Star,
  TrendingUp,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { t } from "@/i18n/messages";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";

interface NavLeaf {
  href: string;
  labelKey: string;
  icon: LucideIcon;
  /** P16/P17 已完整實作的頁;沒這個欄位的頁是 stub */
  implemented?: boolean;
  /** v1.0 為 mock data,v1.1 才接後端 */
  mock?: boolean;
  /** 只有 ADMIN 看得到的 leaf;對應 PLAN § 19.1 RBAC */
  adminOnly?: boolean;
}
interface NavGroup {
  labelKey: string;
  icon: LucideIcon;
  /** 整個群組只有 ADMIN 看得到 */
  adminOnly?: boolean;
  children: NavLeaf[];
}
type NavItem = NavLeaf | NavGroup;

// PLAN § 21:18 頁全部完成
//   - P16 完整接後端 8 頁
//   - P17 完整接後端 10 頁:market(2) + screener/filter + news(2) + portfolio(2) + notifications + admin(2)
//   - P17 mock(v1.1 才補真實) 5 頁:market/calendar / screener/compare / statistics/accuracy / statistics/models / statistics/backtest
const NAV: NavItem[] = [
  {
    href: "/dashboard",
    labelKey: "nav.dashboard",
    icon: LayoutDashboard,
    implemented: true,
  },
  {
    labelKey: "nav.market",
    icon: BarChart3,
    children: [
      { href: "/market/overview", labelKey: "nav.market.overview", icon: TrendingUp, implemented: true },
      { href: "/market/institutional", labelKey: "nav.market.institutional", icon: PieChart, implemented: true },
      { href: "/market/calendar", labelKey: "nav.market.calendar", icon: CalendarDays, implemented: true, mock: true },
    ],
  },
  {
    labelKey: "nav.screener",
    icon: FileSearch,
    children: [
      {
        href: "/screener/watchlist",
        labelKey: "nav.screener.watchlist",
        icon: Star,
        implemented: true,
      },
      { href: "/screener/filter", labelKey: "nav.screener.filter", icon: Filter, implemented: true },
      { href: "/screener/compare", labelKey: "nav.screener.compare", icon: GitCompareArrows, implemented: true, mock: true },
    ],
  },
  {
    labelKey: "nav.analysis",
    icon: Activity,
    children: [
      {
        href: "/analysis/new",
        labelKey: "nav.analysis.new",
        icon: PenSquare,
        implemented: true,
      },
      {
        href: "/analysis/history",
        labelKey: "nav.analysis.history",
        icon: History,
        implemented: true,
      },
    ],
  },
  {
    labelKey: "nav.statistics",
    icon: LineChart,
    children: [
      { href: "/statistics/accuracy", labelKey: "nav.statistics.accuracy", icon: TrendingUp, implemented: true, mock: true },
      { href: "/statistics/models", labelKey: "nav.statistics.models", icon: ListChecks, implemented: true },
      { href: "/statistics/backtest", labelKey: "nav.statistics.backtest", icon: CandlestickChart, implemented: true, mock: true },
    ],
  },
  {
    labelKey: "nav.portfolio",
    icon: Briefcase,
    children: [
      { href: "/portfolio/positions", labelKey: "nav.portfolio.positions", icon: Wallet, implemented: true },
      {
        href: "/portfolio/orders",
        labelKey: "nav.portfolio.orders",
        icon: ListChecks,
        implemented: true,
      },
      { href: "/portfolio/history", labelKey: "nav.portfolio.history", icon: History, implemented: true },
    ],
  },
  {
    labelKey: "nav.news",
    icon: Newspaper,
    children: [
      { href: "/news/sentiment", labelKey: "nav.news.sentiment", icon: Newspaper, implemented: true },
      { href: "/news/announcements", labelKey: "nav.news.announcements", icon: Megaphone, implemented: true },
    ],
  },
  { href: "/notifications", labelKey: "nav.notifications", icon: Bell, implemented: true },
  {
    labelKey: "nav.admin",
    icon: Cog,
    adminOnly: true,
    children: [
      {
        href: "/admin/users",
        labelKey: "nav.admin.users",
        icon: Users,
        adminOnly: true,
        implemented: true,
      },
      {
        href: "/admin/audit",
        labelKey: "nav.admin.audit",
        icon: ScrollText,
        adminOnly: true,
        implemented: true,
      },
      {
        href: "/admin/system",
        labelKey: "nav.admin.system",
        icon: Cog,
        adminOnly: true,
        implemented: true,
        mock: true,
      },
      {
        href: "/admin/pipeline",
        labelKey: "nav.admin.pipeline",
        icon: Database,
        adminOnly: true,
        implemented: true,
      },
    ],
  },
];

function NavLeafLink({
  item,
  isActive,
}: {
  item: NavLeaf;
  isActive: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
        isActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
      )}
      data-implemented={item.implemented ? "true" : "false"}
    >
      <Icon className="h-4 w-4" />
      <span className="flex-1">{t(item.labelKey)}</span>
      {!item.implemented ? (
        <span className="rounded bg-muted px-1 py-0.5 text-[10px] uppercase text-muted-foreground">
          stub
        </span>
      ) : item.mock ? (
        <span
          className="rounded bg-yellow-500/20 px-1 py-0.5 text-[10px] uppercase text-yellow-700 dark:text-yellow-200"
          title="Mock 資料 - v1.1 將完整實作"
        >
          mock
        </span>
      ) : null}
    </Link>
  );
}

function NavGroupBlock({
  group,
  pathname,
}: {
  group: NavGroup;
  pathname: string;
}) {
  const Icon = group.icon;
  const hasActive = group.children.some((c) => pathname.startsWith(c.href));
  const [open, setOpen] = useState(hasActive);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className={cn(
          "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
          hasActive
            ? "text-sidebar-foreground"
            : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
        )}
      >
        <span className="flex items-center gap-2">
          <Icon className="h-4 w-4" />
          {t(group.labelKey)}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform",
            open && "rotate-180",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="ml-3 mt-1 flex flex-col gap-1 border-l pl-3">
        {group.children.map((leaf) => (
          <NavLeafLink
            key={leaf.href}
            item={leaf}
            isActive={pathname.startsWith(leaf.href)}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "ADMIN";
  return (
    <aside className="hidden h-screen w-64 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <CandlestickChart className="h-4 w-4" />
        </div>
        <span className="font-semibold tracking-tight">TradingAgents-TW</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {NAV.map((item, idx) => {
          if ("children" in item) {
            if (item.adminOnly && !isAdmin) return null;
            const visible = item.adminOnly
              ? item
              : {
                  ...item,
                  children: item.children.filter(
                    (c) => !c.adminOnly || isAdmin,
                  ),
                };
            return (
              <NavGroupBlock key={idx} group={visible} pathname={pathname} />
            );
          }
          if (item.adminOnly && !isAdmin) return null;
          return (
            <NavLeafLink
              key={item.href}
              item={item}
              isActive={pathname.startsWith(item.href)}
            />
          );
        })}
      </nav>
    </aside>
  );
}

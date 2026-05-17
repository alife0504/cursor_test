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
import { cn } from "@/lib/utils";

interface NavLeaf {
  href: string;
  labelKey: string;
  icon: LucideIcon;
}
interface NavGroup {
  labelKey: string;
  icon: LucideIcon;
  children: NavLeaf[];
}
type NavItem = NavLeaf | NavGroup;

// 對應 PLAN § 21 完整 18 頁
const NAV: NavItem[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  {
    labelKey: "nav.market",
    icon: BarChart3,
    children: [
      { href: "/market/overview", labelKey: "nav.market.overview", icon: TrendingUp },
      { href: "/market/institutional", labelKey: "nav.market.institutional", icon: PieChart },
      { href: "/market/calendar", labelKey: "nav.market.calendar", icon: CalendarDays },
    ],
  },
  {
    labelKey: "nav.screener",
    icon: FileSearch,
    children: [
      { href: "/screener/watchlist", labelKey: "nav.screener.watchlist", icon: Star },
      { href: "/screener/filter", labelKey: "nav.screener.filter", icon: Filter },
      { href: "/screener/compare", labelKey: "nav.screener.compare", icon: GitCompareArrows },
    ],
  },
  {
    labelKey: "nav.analysis",
    icon: Activity,
    children: [
      { href: "/analysis/new", labelKey: "nav.analysis.new", icon: PenSquare },
      { href: "/analysis/history", labelKey: "nav.analysis.history", icon: History },
    ],
  },
  {
    labelKey: "nav.statistics",
    icon: LineChart,
    children: [
      { href: "/statistics/accuracy", labelKey: "nav.statistics.accuracy", icon: TrendingUp },
      { href: "/statistics/models", labelKey: "nav.statistics.models", icon: ListChecks },
      { href: "/statistics/backtest", labelKey: "nav.statistics.backtest", icon: CandlestickChart },
    ],
  },
  {
    labelKey: "nav.portfolio",
    icon: Briefcase,
    children: [
      { href: "/portfolio/positions", labelKey: "nav.portfolio.positions", icon: Wallet },
      { href: "/portfolio/orders", labelKey: "nav.portfolio.orders", icon: ListChecks },
      { href: "/portfolio/history", labelKey: "nav.portfolio.history", icon: History },
    ],
  },
  {
    labelKey: "nav.news",
    icon: Newspaper,
    children: [
      { href: "/news/sentiment", labelKey: "nav.news.sentiment", icon: Newspaper },
      { href: "/news/announcements", labelKey: "nav.news.announcements", icon: Megaphone },
    ],
  },
  { href: "/notifications", labelKey: "nav.notifications", icon: Bell },
  {
    labelKey: "nav.admin",
    icon: Cog,
    children: [
      { href: "/admin/users", labelKey: "nav.admin.users", icon: Users },
      { href: "/admin/audit", labelKey: "nav.admin.audit", icon: ScrollText },
      { href: "/admin/system", labelKey: "nav.admin.system", icon: Cog },
      { href: "/admin/pipeline", labelKey: "nav.admin.pipeline", icon: Database },
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
    >
      <Icon className="h-4 w-4" />
      <span>{t(item.labelKey)}</span>
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
  return (
    <aside className="hidden h-screen w-64 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <CandlestickChart className="h-4 w-4" />
        </div>
        <span className="font-semibold tracking-tight">TradingAgents-TW</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {NAV.map((item, idx) =>
          "children" in item ? (
            <NavGroupBlock key={idx} group={item} pathname={pathname} />
          ) : (
            <NavLeafLink
              key={item.href}
              item={item}
              isActive={pathname.startsWith(item.href)}
            />
          ),
        )}
      </nav>
    </aside>
  );
}

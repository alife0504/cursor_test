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
  Sparkles,
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { t } from "@/i18n/messages";
import { useAuthStore } from "@/store/auth";
import { useUiStore } from "@/store/ui";
import { cn } from "@/lib/utils";

interface NavLeaf {
  href: string;
  labelKey: string;
  icon: LucideIcon;
  /** P16/P17 已完整實作的頁；沒這個欄位的頁是 stub */
  implemented?: boolean;
  /** v1.0 為 mock data，v1.1 才接後端 */
  mock?: boolean;
  /** 只有 ADMIN 看得到的 leaf；對應 PLAN § 19.1 RBAC */
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

// PLAN § 21：18 頁全部完成
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
      { href: "/statistics/backtest", labelKey: "nav.statistics.backtest", icon: Sparkles, implemented: true, mock: true },
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
  onNavigate,
}: {
  item: NavLeaf;
  isActive: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "group/nav flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-all",
        isActive
          ? "bg-sidebar-primary/15 text-sidebar-primary-foreground ring-1 ring-sidebar-primary/20 shadow-sm"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground",
      )}
      data-implemented={item.implemented ? "true" : "false"}
      aria-current={isActive ? "page" : undefined}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 transition-colors",
          isActive
            ? "text-sidebar-primary"
            : "text-sidebar-foreground/60 group-hover/nav:text-sidebar-foreground",
        )}
      />
      <span className="flex-1 truncate">{t(item.labelKey)}</span>
      {!item.implemented ? (
        <span className="rounded bg-muted/30 px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
          stub
        </span>
      ) : item.mock ? (
        <span
          className="rounded bg-warning/20 px-1.5 py-0.5 text-[10px] font-medium uppercase text-warning"
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
  onNavigate,
}: {
  group: NavGroup;
  pathname: string;
  onNavigate?: () => void;
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
            : "text-sidebar-foreground/80 hover:bg-sidebar-accent",
        )}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-sidebar-foreground/60" />
          {t(group.labelKey)}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="ml-3 mt-1 flex flex-col gap-1 border-l border-sidebar-border pl-3">
        {group.children.map((leaf) => (
          <NavLeafLink
            key={leaf.href}
            item={leaf}
            isActive={pathname.startsWith(leaf.href)}
            onNavigate={onNavigate}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

function SidebarBrand() {
  return (
    <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground shadow-glow">
        <CandlestickChart className="h-4 w-4" />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="font-semibold tracking-tight text-sidebar-foreground">
          TradingAgents
        </span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-sidebar-foreground/50">
          TW Edition
        </span>
      </div>
    </div>
  );
}

function NavList({
  pathname,
  isAdmin,
  onNavigate,
}: {
  pathname: string;
  isAdmin: boolean;
  onNavigate?: () => void;
}) {
  return (
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
            <NavGroupBlock
              key={idx}
              group={visible}
              pathname={pathname}
              onNavigate={onNavigate}
            />
          );
        }
        if (item.adminOnly && !isAdmin) return null;
        return (
          <NavLeafLink
            key={item.href}
            item={item}
            isActive={pathname.startsWith(item.href)}
            onNavigate={onNavigate}
          />
        );
      })}
    </nav>
  );
}

function SidebarFooter({ role }: { role?: string }) {
  return (
    <div className="border-t border-sidebar-border p-3 text-[10px] text-sidebar-foreground/50">
      <div className="flex items-center justify-between">
        <span>v1.0 · {role ?? "—"}</span>
        <span className="rounded bg-sidebar-accent px-1.5 py-0.5">Self-host</span>
      </div>
    </div>
  );
}

/** 桌機固定 Sidebar（>= md），Mobile 用下面 MobileSidebar Sheet。 */
export function Sidebar() {
  const pathname = usePathname();
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "ADMIN";
  return (
    <aside className="hidden h-screen w-56 shrink-0 flex-col border-r border-sidebar-border bg-brand-gradient text-sidebar-foreground md:flex">
      <SidebarBrand />
      <NavList pathname={pathname} isAdmin={isAdmin} />
      <SidebarFooter role={role} />
    </aside>
  );
}

/** Mobile Sheet 版本，由 Topbar 的漢堡 trigger 經 useUiStore 控制。 */
export function MobileSidebar() {
  const pathname = usePathname();
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "ADMIN";
  const open = useUiStore((s) => s.mobileNavOpen);
  const setOpen = useUiStore((s) => s.setMobileNavOpen);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent
        side="left"
        className="w-72 max-w-[80vw] bg-brand-gradient text-sidebar-foreground p-0"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>主選單</SheetTitle>
          <SheetDescription>網站導覽</SheetDescription>
        </SheetHeader>
        <SidebarBrand />
        <NavList
          pathname={pathname}
          isAdmin={isAdmin}
          onNavigate={() => setOpen(false)}
        />
        <SidebarFooter role={role} />
      </SheetContent>
    </Sheet>
  );
}

"use client";

import { ChevronRight, Home } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import { cn } from "@/lib/utils";

/**
 * 從 pathname 自動產生繁中麵包屑。
 * - 第一段固定 "儀表板" / Home icon → /dashboard
 * - 動態 id（UUID）顯示為 "詳情"
 */
const LABELS: Record<string, string> = {
  dashboard: "儀表板",
  market: "市場",
  overview: "市場總覽",
  institutional: "三大法人",
  calendar: "財報日曆",
  screener: "選股",
  watchlist: "自選股清單",
  filter: "選股篩選",
  compare: "多股比較",
  analysis: "AI 分析",
  new: "新增分析",
  history: "分析歷史",
  statistics: "績效統計",
  accuracy: "準確率分析",
  models: "模型比較",
  backtest: "回測結果",
  portfolio: "投資組合",
  positions: "模擬持倉",
  orders: "待核准訂單",
  news: "資訊",
  sentiment: "新聞情緒",
  announcements: "重大公告",
  notifications: "通知設定",
  admin: "管理",
  users: "用戶管理",
  audit: "審計日誌",
  system: "系統監控",
  pipeline: "資料管線",
};

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface Crumb {
  href: string;
  label: string;
  isLast: boolean;
}

function buildCrumbs(pathname: string): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return [];

  const crumbs: Crumb[] = [];
  let acc = "";
  parts.forEach((p, i) => {
    acc += `/${p}`;
    const isLast = i === parts.length - 1;
    let label = LABELS[p];
    if (!label) {
      if (UUID_RE.test(p)) {
        label = "詳情";
      } else {
        label = p;
      }
    }
    crumbs.push({ href: acc, label, isLast });
  });
  return crumbs;
}

export function Breadcrumbs({
  className,
  alwaysShow = false,
}: {
  className?: string;
  /** true：單層（如 /dashboard）也顯示 — Topbar 內嵌用，避免左側空蕩 */
  alwaysShow?: boolean;
}) {
  const pathname = usePathname();
  const crumbs = useMemo(() => buildCrumbs(pathname || ""), [pathname]);

  // dashboard 自己一個頁預設不顯麵包屑
  if (crumbs.length === 0 || (!alwaysShow && crumbs.length <= 1)) return null;

  return (
    <nav
      aria-label="麵包屑"
      className={cn(
        "flex items-center gap-1 text-xs text-muted-foreground",
        className,
      )}
    >
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-muted hover:text-foreground"
      >
        <Home className="h-3 w-3" />
        <span className="sr-only">首頁</span>
      </Link>
      {crumbs.map((c) => (
        <span key={c.href} className="flex items-center gap-1">
          <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
          {c.isLast ? (
            <span aria-current="page" className="font-medium text-foreground">
              {c.label}
            </span>
          ) : (
            <Link
              href={c.href}
              className="rounded px-1 py-0.5 hover:bg-muted hover:text-foreground"
            >
              {c.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}

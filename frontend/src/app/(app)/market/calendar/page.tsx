"use client";

import { Banknote, CalendarDays, FileText, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { KpiCard } from "@/components/common/KpiCard";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { useMarketCalendar } from "@/hooks/useMarket";
import type { CalendarEvent, CalendarEventType } from "@/lib/api-types";
import { cn } from "@/lib/utils";

// 財報日曆（真實資料）
//   - GET /api/v1/market/calendar?from&to
//   - 真實事件：法定申報期限（依證交法 §36 推算）+ 除權息（FinMind 本地庫）
//     + 股東會（tw-hawk/twofc 本地資料湖，含真實公告日）
//   - 刻意不做「法說會」：無穩定 dataset，不顯示勝過顯示假資料

const TYPE_LABEL: Record<string, string> = {
  filing_deadline: "法定申報期限",
  ex_dividend: "除權息",
  shareholder_meeting: "股東會",
  us_econ: "美國數據",
};
const TYPE_COLOR: Record<string, string> = {
  filing_deadline: "bg-info/15 text-info",
  ex_dividend: "bg-bull-muted text-bull",
  shareholder_meeting: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
  us_econ: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
};

// 每日多筆、逐檔的事件類型 → 收合成「1 筆 + 其餘 N 筆 ▾」；其餘（法定期限/美國數據）逐筆顯示
const COLLAPSIBLE_TYPES: CalendarEventType[] = ["ex_dividend", "shareholder_meeting"];

/** 每日多筆、逐檔的事件類型（除權息/股東會）各自收合成「1 筆 + 其餘 N 筆 ▾」。 */
function CollapsibleGroup({ events }: { events: CalendarEvent[] }) {
  const [open, setOpen] = useState(false);
  const shown = open ? events : events.slice(0, 1);
  const cls = TYPE_COLOR[events[0].event_type] ?? "bg-muted";
  return (
    <>
      {shown.map((e, i) => (
        <div
          key={`${e.event_type}-${e.symbol ?? ""}-${i}`}
          className={cn("truncate rounded px-1 py-0.5 text-[10px]", cls)}
          title={`${e.title}（${TYPE_LABEL[e.event_type] ?? e.event_type}）`}
        >
          {e.symbol ? `${e.symbol} ${e.name ?? ""}` : e.title}
        </div>
      ))}
      {events.length > 1 ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className={cn("w-full truncate rounded px-1 py-0.5 text-left text-[10px] opacity-80 hover:opacity-100", cls)}
        >
          {open ? "收合 ▴" : `其餘 ${events.length - 1} 筆 ▾`}
        </button>
      ) : null}
    </>
  );
}

/** 單一格內的事件顯示：逐檔事件（除權息/股東會）各自收合；其餘逐筆顯示。 */
function DayEvents({ events }: { events: CalendarEvent[] }) {
  const others = events.filter((e) => !COLLAPSIBLE_TYPES.includes(e.event_type));
  const groups = COLLAPSIBLE_TYPES.map((t) =>
    events.filter((e) => e.event_type === t),
  ).filter((g) => g.length > 0);

  return (
    <div className="mt-1 space-y-1">
      {others.map((e, i) => (
        <div
          key={`${e.event_type}-${e.symbol ?? ""}-${i}`}
          className={cn(
            "truncate rounded px-1 py-0.5 text-[10px]",
            TYPE_COLOR[e.event_type] ?? "bg-muted",
          )}
          title={`${e.title}（${TYPE_LABEL[e.event_type] ?? e.event_type}）`}
        >
          {e.symbol ? `${e.symbol} ${e.name ?? ""}` : e.title}
        </div>
      ))}
      {groups.map((g) => (
        <CollapsibleGroup key={g[0].event_type} events={g} />
      ))}
    </div>
  );
}

function monthRange(year: number, month: number): { from: string; to: string } {
  const last = new Date(year, month + 1, 0).getDate();
  const mm = String(month + 1).padStart(2, "0");
  return { from: `${year}-${mm}-01`, to: `${year}-${mm}-${String(last).padStart(2, "0")}` };
}

export default function MarketCalendarPage() {
  const today = new Date();
  const [cursor, setCursor] = useState({
    year: today.getFullYear(),
    month: today.getMonth(),
  });

  const { from, to } = useMemo(
    () => monthRange(cursor.year, cursor.month),
    [cursor.year, cursor.month],
  );
  // 區分載入中／故障／成功但空：不可把三者都畫成「本月無排程事件」空狀態（故障看起來像沒事件）
  const { data, isLoading, error, refetch } = useMarketCalendar(from, to);
  const events = useMemo(() => data ?? [], [data]);

  const counts = useMemo(
    () => ({
      total: events.length,
      filing: events.filter((e) => e.event_type === "filing_deadline").length,
      exDiv: events.filter((e) => e.event_type === "ex_dividend").length,
      agm: events.filter((e) => e.event_type === "shareholder_meeting").length,
      usEcon: events.filter((e) => e.event_type === "us_econ").length,
    }),
    [events],
  );

  const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate();
  const firstDay = new Date(cursor.year, cursor.month, 1).getDay();
  const cells: Array<{ day?: number; events: CalendarEvent[] }> = [];
  for (let i = 0; i < firstDay; i++) cells.push({ events: [] });
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${cursor.year}-${String(cursor.month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({
      day: d,
      events: events.filter((e) => e.event_date === dateStr),
    });
  }

  const prevMonth = () =>
    setCursor((c) =>
      c.month === 0 ? { year: c.year - 1, month: 11 } : { ...c, month: c.month - 1 },
    );
  const nextMonth = () =>
    setCursor((c) =>
      c.month === 11 ? { year: c.year + 1, month: 0 } : { ...c, month: c.month + 1 },
    );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={CalendarDays}
        title="財報日曆"
        description="法定申報期限、除權息、股東會、美國重大數據（台北時間）"
      />

      {/* 本月事件摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <KpiCard
          title="本月事件"
          value={counts.total}
          subtitle="所有類型合計"
          icon={CalendarDays}
          accent="primary"
        />
        <KpiCard
          title="法定申報期限"
          value={counts.filing}
          subtitle="依證交法 §36"
          icon={FileText}
          accent="info"
        />
        <KpiCard
          title="除權息"
          value={counts.exDiv}
          subtitle="配息配股"
          icon={Banknote}
          accent="bull"
        />
        <KpiCard
          title="股東會"
          value={counts.agm}
          subtitle="tw-hawk 公告日"
          icon={Users}
          accent="warning"
        />
        <KpiCard
          title="美國數據"
          value={counts.usEcon}
          subtitle="FOMC / 非農 / ISM"
          icon={CalendarDays}
          accent="primary"
        />
      </section>

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {cursor.year} 年 {cursor.month + 1} 月
        </h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={prevMonth}>← 上月</Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCursor({ year: today.getFullYear(), month: today.getMonth() })}
          >
            今天
          </Button>
          <Button variant="outline" size="sm" onClick={nextMonth}>下月 →</Button>
        </div>
      </div>

      {isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : error ? (
        <ErrorState
          title="財報日曆載入失敗"
          description="請稍後再試，或確認後端服務是否正常。"
          error={error}
          onRetry={() => {
            void refetch();
          }}
        />
      ) : events.length === 0 ? (
        <EmptyState title="本月無排程事件" />
      ) : (
        <div className="grid grid-cols-7 gap-1 text-xs">
          {["日", "一", "二", "三", "四", "五", "六"].map((d) => (
            <div key={d} className="p-1 text-center font-medium text-muted-foreground">
              {d}
            </div>
          ))}
          {cells.map((cell, idx) => (
            <div
              key={idx}
              className={cn(
                "min-h-[80px] rounded-md border p-1",
                cell.day ? "bg-card" : "bg-muted/30",
              )}
            >
              {cell.day ? (
                <>
                  <div className="text-right text-xs text-muted-foreground tabular-nums">
                    {cell.day}
                  </div>
                  <DayEvents events={cell.events} />
                </>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

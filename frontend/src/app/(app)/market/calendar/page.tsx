"use client";

import { Banknote, CalendarDays, FileText } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { useMarketCalendar } from "@/hooks/useMarket";
import type { CalendarEvent } from "@/lib/api-types";
import { cn } from "@/lib/utils";

// 財報日曆（真實資料）
//   - GET /api/v1/market/calendar?from&to
//   - 兩類真實事件：法定申報期限（依證交法 §36 推算）+ 除權息（FinMind 本地庫）
//   - 刻意不做「股東會 / 法說會」：FinMind 無此 dataset，不顯示勝過顯示假資料

const TYPE_LABEL: Record<string, string> = {
  filing_deadline: "法定申報期限",
  ex_dividend: "除權息",
  us_econ: "美國數據",
};
const TYPE_COLOR: Record<string, string> = {
  filing_deadline: "bg-info/15 text-info",
  ex_dividend: "bg-bull-muted text-bull",
  us_econ: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
};

/** 單一格內的事件顯示：除權息若很多家 → 只顯示 1 家 + 「其餘 N 家 ▾」可展開。 */
function DayEvents({ events }: { events: CalendarEvent[] }) {
  const [open, setOpen] = useState(false);
  const exDiv = events.filter((e) => e.event_type === "ex_dividend");
  const others = events.filter((e) => e.event_type !== "ex_dividend");

  const pill = (e: CalendarEvent, i: number) => (
    <div
      key={`${e.event_type}-${e.symbol ?? ""}-${i}`}
      className={cn("truncate rounded px-1 py-0.5 text-[10px]", TYPE_COLOR[e.event_type] ?? "bg-muted")}
      title={`${e.title}（${TYPE_LABEL[e.event_type] ?? e.event_type}）`}
    >
      {e.symbol ? `${e.symbol} ${e.name ?? ""}` : e.title}
    </div>
  );

  const shownExDiv = open ? exDiv : exDiv.slice(0, 1);
  return (
    <div className="mt-1 space-y-1">
      {others.map((e, i) => pill(e, i))}
      {shownExDiv.map((e, i) => pill(e, i))}
      {exDiv.length > 1 ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="w-full truncate rounded bg-bull-muted/60 px-1 py-0.5 text-left text-[10px] text-bull hover:bg-bull-muted"
        >
          {open ? "收合 ▴" : `其餘 ${exDiv.length - 1} 家 ▾`}
        </button>
      ) : null}
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
  const query = useMarketCalendar(from, to);
  const events = useMemo(() => query.data ?? [], [query.data]);

  const counts = useMemo(
    () => ({
      total: events.length,
      filing: events.filter((e) => e.event_type === "filing_deadline").length,
      exDiv: events.filter((e) => e.event_type === "ex_dividend").length,
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
        description="法定申報期限、除權息、美國重大數據（台北時間）"
      />

      {/* 本月事件摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
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

      {events.length === 0 ? (
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

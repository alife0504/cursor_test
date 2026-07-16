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

type EventType = "filing_deadline" | "ex_dividend";

const TYPE_LABEL: Record<EventType, string> = {
  filing_deadline: "法定申報期限",
  ex_dividend: "除權息",
};
const TYPE_COLOR: Record<EventType, string> = {
  filing_deadline: "bg-info/15 text-info",
  ex_dividend: "bg-bull-muted text-bull",
};

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
        description="法定申報期限與除權息時程（真實資料）"
      />

      {/* 本月事件摘要 KPI 帶 */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
                  <div className="mt-1 space-y-1">
                    {cell.events.map((e, i) => (
                      <div
                        key={i}
                        className={cn(
                          "truncate rounded px-1 py-0.5 text-[10px]",
                          TYPE_COLOR[e.event_type],
                        )}
                        title={`${e.title}（${TYPE_LABEL[e.event_type]}）`}
                      >
                        {/* 法定申報期限是全市場事件、無個股代號 → 直接顯示標題 */}
                        {e.symbol ? `${e.symbol} ${e.name ?? ""}` : e.title}
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { Banknote, CalendarDays, FileText, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { KpiCard } from "@/components/common/KpiCard";
import { MockBanner } from "@/components/common/MockBanner";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Phase 17 § D:財報日曆(mock,v1.1)
//   - 月曆 view
//   - mock:未來 30 天 fake events
//   - 標示 "Mock - v1.1"

interface MockEvent {
  date: string; // yyyy-mm-dd
  symbol: string;
  name: string;
  type: "earnings" | "ex_dividend" | "shareholder_meeting";
  title: string;
}

const MOCK_SYMBOLS: Array<[string, string]> = [
  ["2330", "台積電"],
  ["2317", "鴻海"],
  ["2454", "聯發科"],
  ["2412", "中華電"],
  ["1303", "南亞"],
  ["AAPL", "Apple"],
  ["MSFT", "Microsoft"],
  ["NVDA", "NVIDIA"],
];

const TYPE_LABEL: Record<MockEvent["type"], string> = {
  earnings: "法說 / 財報",
  ex_dividend: "除權息",
  shareholder_meeting: "股東會",
};
const TYPE_COLOR: Record<MockEvent["type"], string> = {
  earnings: "bg-info/15 text-info",
  ex_dividend: "bg-bull-muted text-bull",
  shareholder_meeting: "bg-warning/15 text-warning",
};

function buildMockEvents(year: number, month: number): MockEvent[] {
  // deterministic mock,基於 year-month seed
  const events: MockEvent[] = [];
  const types: MockEvent["type"][] = [
    "earnings",
    "ex_dividend",
    "shareholder_meeting",
  ];
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  for (let i = 0; i < 12; i++) {
    const day = ((i * 7 + (year + month)) % daysInMonth) + 1;
    const [sym, name] = MOCK_SYMBOLS[i % MOCK_SYMBOLS.length];
    const type = types[i % 3];
    events.push({
      date: `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      symbol: sym,
      name,
      type,
      title: `${name} ${TYPE_LABEL[type]}`,
    });
  }
  return events;
}

export default function MarketCalendarPage() {
  const today = new Date();
  const [cursor, setCursor] = useState({
    year: today.getFullYear(),
    month: today.getMonth(),
  });

  const events = useMemo(
    () => buildMockEvents(cursor.year, cursor.month),
    [cursor.year, cursor.month],
  );

  const counts = useMemo(
    () => ({
      total: events.length,
      earnings: events.filter((e) => e.type === "earnings").length,
      exDiv: events.filter((e) => e.type === "ex_dividend").length,
      meeting: events.filter((e) => e.type === "shareholder_meeting").length,
    }),
    [events],
  );

  const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate();
  const firstDay = new Date(cursor.year, cursor.month, 1).getDay();
  const cells: Array<{ day?: number; events: MockEvent[] }> = [];
  for (let i = 0; i < firstDay; i++) cells.push({ events: [] });
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${cursor.year}-${String(cursor.month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({
      day: d,
      events: events.filter((e) => e.date === dateStr),
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
        description="法說會、除權息、股東會時程"
      />

      <MockBanner trackingRef="v1.1 接 GET /api/v1/market/calendar 真實資料" />

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
          title="法說 / 財報"
          value={counts.earnings}
          subtitle="業績發表"
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
          value={counts.meeting}
          subtitle="股東大會"
          icon={Users}
          accent="warning"
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
                          TYPE_COLOR[e.type],
                        )}
                        title={e.title}
                      >
                        {e.symbol} {e.name}
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

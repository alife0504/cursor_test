"use client";

import { ExternalLink, Megaphone } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useMaterialEvents, useStockAnnouncements } from "@/hooks/useNews";

// tw-hawk twofc_events 類型 → 中文
const EVENT_LABEL: Record<string, string> = {
  board_resolution: "董事會決議",
  material_other: "其他重大訊息",
  dividend_decision: "股利決議",
  dividend_schedule: "除權息時程",
  asset_disposal: "資產處分",
  capital_increase: "增資",
  exec_change: "經理人異動",
  endorsement_guarantee: "背書保證",
  subsidiary_notice: "子公司訊息",
  earnings_call: "法說會",
  shareholder_meeting: "股東會",
};

// Phase 17 § M:重大公告
//   - 後端僅有個股 /stocks/{symbol}/announcements
//   - 全市場 view v1.1 補

export default function NewsAnnouncementsPage() {
  const [symbol, setSymbol] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");

  const { data, isLoading, error, refetch } = useStockAnnouncements({
    symbol,
    limit: 100,
    enabled: Boolean(symbol),
  });
  const { data: events } = useMaterialEvents({
    symbol,
    enabled: Boolean(symbol),
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((row) => {
      // 用「包含」比對：DB 的 announcement_type 是 TWSE 條款代碼（如「第51款」），
      // 精確比對會讓使用者輸入任何關鍵字都落空。
      if (
        typeFilter &&
        !(row.announcement_type ?? "").includes(typeFilter.trim())
      )
        return false;
      if (from && row.published_at && row.published_at < from) return false;
      if (to && row.published_at && row.published_at > `${to}T23:59:59Z`) return false;
      return true;
    });
  }, [data, typeFilter, from, to]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={Megaphone}
        title="重大公告"
        description="台股重大訊息 · TWSE 每日公告（依股票查詢）"
      />

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">股票</Label>
          <StockPicker
            value={symbol || null}
            onSelect={(s) => setSymbol(s.symbol)}
            triggerLabel={symbol || undefined}
            placeholder="搜尋"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ann-type" className="text-xs">類型</Label>
          <Input
            id="ann-type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            placeholder="例:第51款 / 第20款"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ann-from" className="text-xs">起始日</Label>
          <Input
            id="ann-from"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ann-to" className="text-xs">結束日</Label>
          <Input
            id="ann-to"
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
      </div>

      {!symbol ? (
        <EmptyState
          title="請先選擇個股"
          description="輸入代號或名稱查詢該股票的公告"
        />
      ) : isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : error ? (
        // 已選股但後端故障：給明確錯誤 + 重試，而非顯示「該條件下無公告」（誤導成該股無公告）
        <ErrorState
          title="公告載入失敗"
          description="請稍後再試，或確認後端服務是否正常。"
          error={error}
          onRetry={() => {
            void refetch();
          }}
        />
      ) : filtered.length === 0 ? (
        <EmptyState title="該條件下無公告" />
      ) : (
        <div className="rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-2">日期</th>
                <th className="p-2">代號</th>
                <th className="p-2">類型</th>
                <th className="p-2">標題</th>
                <th className="p-2 w-10" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, idx) => (
                <tr key={(row.id ?? idx) + row.title.slice(0, 20)} className="border-b">
                  <td className="p-2 tabular-nums">{row.published_at?.slice(0, 10) ?? "-"}</td>
                  <td className="p-2 font-mono">{row.symbol ?? "-"}</td>
                  <td className="p-2 text-muted-foreground">{row.announcement_type ?? "-"}</td>
                  <td className="p-2">{row.title}</td>
                  <td className="p-2">
                    {row.url ? (
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {symbol && (events?.length ?? 0) > 0 ? (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">
            重大訊息{" "}
            <span className="text-xs font-normal text-muted-foreground">
              （tw-hawk · MOPS 重大訊息，含真實公告日）
            </span>
          </h3>
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="p-2">公告日</th>
                  <th className="p-2">類型</th>
                  <th className="p-2">主旨</th>
                </tr>
              </thead>
              <tbody>
                {events?.map((e, i) => (
                  <tr key={`${e.announced_at}-${i}`} className="border-b">
                    <td className="p-2 tabular-nums">
                      {e.announced_at?.slice(0, 10) ?? "-"}
                    </td>
                    <td className="p-2 text-muted-foreground">
                      {EVENT_LABEL[e.event_type] ?? e.event_type}
                    </td>
                    <td className="p-2">{e.title}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

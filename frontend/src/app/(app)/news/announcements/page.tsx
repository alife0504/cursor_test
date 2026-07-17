"use client";

import { ExternalLink, Megaphone } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useStockAnnouncements } from "@/hooks/useNews";

// Phase 17 § M:重大公告
//   - 後端僅有個股 /stocks/{symbol}/announcements
//   - 全市場 view v1.1 補

export default function NewsAnnouncementsPage() {
  const [symbol, setSymbol] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");

  const { data, isLoading } = useStockAnnouncements({
    symbol,
    limit: 100,
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
    </div>
  );
}

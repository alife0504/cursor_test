"use client";

import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { SentimentBar } from "@/components/news/SentimentBar";
import { useStockNews } from "@/hooks/useNews";

// Phase 17 § L:新聞情緒
//   - 後端僅有「個股 /stocks/{symbol}/news」endpoint
//   - 提供個股檢視 + sentiment 分佈
//   - 全市場聚合留 v1.1

// 情緒色：positive → bull（紅、台股慣例「利多」）；negative → bear（綠）；neutral → 灰
const SENTIMENT_LABEL_MAP: Record<string, { text: string; color: string }> = {
  very_positive: { text: "極正面", color: "text-bull bg-bull-muted" },
  positive: { text: "正面", color: "text-bull bg-bull-muted" },
  neutral: { text: "中性", color: "text-muted-foreground bg-muted" },
  negative: { text: "負面", color: "text-bear bg-bear-muted" },
  very_negative: { text: "極負面", color: "text-bear bg-bear-muted" },
};

export default function NewsSentimentPage() {
  const [symbol, setSymbol] = useState<string>("");
  const { data, isLoading } = useStockNews({
    symbol,
    limit: 50,
    enabled: Boolean(symbol),
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="新聞情緒"
        description="個股近期新聞與情緒分佈（資料來源：Qdrant + 各家新聞 source）"
      />

      <div className="flex items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">選擇個股</span>
          <StockPicker
            value={symbol || null}
            onSelect={(s) => setSymbol(s.symbol)}
            placeholder="輸入代號或名稱搜尋"
            triggerLabel={symbol || undefined}
            className="w-72"
          />
        </div>
        {symbol ? (
          <span className="text-sm text-muted-foreground">
            目前查看:<span className="font-mono">{symbol}</span>
          </span>
        ) : null}
      </div>

      {!symbol ? (
        <EmptyState
          title="請先選擇個股"
          description="從上方搜尋框選股票後將顯示新聞與情緒分佈"
        />
      ) : isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="此股票近期無新聞" />
      ) : (
        <>
          <SentimentBar items={data} />
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="p-2">情緒</th>
                  <th className="p-2">標題</th>
                  <th className="p-2">來源</th>
                  <th className="p-2">時間</th>
                  <th className="p-2 w-10" />
                </tr>
              </thead>
              <tbody>
                {data.map((it, idx) => {
                  const lbl = it.sentiment_label ?? "neutral";
                  const tag = SENTIMENT_LABEL_MAP[lbl] ?? SENTIMENT_LABEL_MAP.neutral;
                  return (
                    <tr key={(it.id ?? idx) + it.title.slice(0, 20)} className="border-b">
                      <td className="p-2">
                        <span className={`inline-block rounded px-1.5 py-0.5 text-xs ${tag.color}`}>
                          {tag.text}
                        </span>
                      </td>
                      <td className="p-2">{it.title}</td>
                      <td className="p-2 text-muted-foreground">{it.source ?? "-"}</td>
                      <td className="p-2 text-xs text-muted-foreground tabular-nums">
                        {it.published_at?.slice(0, 16) ?? "-"}
                      </td>
                      <td className="p-2">
                        {it.url ? (
                          <a
                            href={it.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

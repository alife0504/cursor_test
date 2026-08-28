"use client";

import { ExternalLink, Newspaper } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { SentimentBar } from "@/components/news/SentimentBar";
import { useStockNews, useTwSentiment } from "@/hooks/useNews";

// Phase 17 § L:新聞情緒
//   - 後端僅有「個股 /stocks/{symbol}/news」endpoint
//   - 提供個股檢視 + sentiment 分佈
//   - 全市場聚合留 v1.1

// 情緒色：positive → bull（紅、台股慣例「利多」）；negative → bear（綠）；neutral → 灰。
// DB 實際只有 positive/neutral/negative/unknown 四值；unknown = 未評級（無法判定），
// 不可 fallback 成「中性」（會與情緒分佈圖自相矛盾）。
const SENTIMENT_LABEL_MAP: Record<string, { text: string; color: string }> = {
  positive: { text: "正面", color: "text-bull bg-bull-muted" },
  neutral: { text: "中性", color: "text-muted-foreground bg-muted" },
  negative: { text: "負面", color: "text-bear bg-bear-muted" },
  unknown: { text: "未評級", color: "text-muted-foreground bg-muted/50" },
};

export default function NewsSentimentPage() {
  const [symbol, setSymbol] = useState<string>("");
  const { data, isLoading, error, refetch } = useStockNews({
    symbol,
    limit: 50,
    enabled: Boolean(symbol),
  });
  const { data: twSent } = useTwSentiment({
    symbol,
    enabled: Boolean(symbol),
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={Newspaper}
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
      ) : error ? (
        // 已選股但後端故障：給明確錯誤 + 重試，而非顯示「此股票近期無新聞」（誤導成該股無新聞）
        <ErrorState
          title="新聞載入失敗"
          description="請稍後再試，或確認後端服務是否正常。"
          error={error}
          onRetry={() => {
            void refetch();
          }}
        />
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
                  const lbl = it.sentiment ?? it.sentiment_label ?? "unknown";
                  const tag = SENTIMENT_LABEL_MAP[lbl] ?? SENTIMENT_LABEL_MAP.unknown;
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

      {symbol && (twSent?.length ?? 0) > 0 ? (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">
            每日情緒{" "}
            <span className="text-xs font-normal text-muted-foreground">
              （tw-hawk · 情緒分數/AI 摘要/討論熱度）
            </span>
          </h3>
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="p-2">日期</th>
                  <th className="p-2">情緒分數</th>
                  <th className="p-2">討論熱度</th>
                  <th className="p-2">摘要</th>
                </tr>
              </thead>
              <tbody>
                {twSent?.map((s, i) => {
                  const sc = s.sentiment_score ?? 0;
                  const cls = sc > 0 ? "text-bull" : sc < 0 ? "text-bear" : "";
                  return (
                    <tr key={`${s.date}-${i}`} className="border-b">
                      <td className="p-2 tabular-nums">{s.date}</td>
                      <td className={`p-2 num tabular-nums ${cls}`}>
                        {s.sentiment_score?.toFixed(2) ?? "-"}
                      </td>
                      <td className="p-2 tabular-nums text-muted-foreground">
                        {s.discussion_volume ?? "-"}
                      </td>
                      <td className="p-2">{s.short_summary ?? "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

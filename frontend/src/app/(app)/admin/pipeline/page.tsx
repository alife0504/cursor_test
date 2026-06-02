"use client";

import { AlertCircle, CheckCircle2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useDLQ,
  useRequeueDLQ,
  useResolveDLQ,
} from "@/hooks/useSystem";
import type { DLQItem } from "@/lib/api-types";

// Phase 17 § P:資料管線管理
//   - DLQ 列表
//   - resolve / requeue 按鈕
//   - 每個 source 的 last success time(後端目前沒專屬 endpoint → 顯示「需 P19/P20」)
//   - 手動觸發 task buttons(後端尚未開放 → button 暫顯示 "尚未開放 v1.1")
//   - PLAN 已知陷阱:DLQ resolve requireConfirm + 顯示原始 traceback

export default function AdminPipelinePage() {
  const [showResolved, setShowResolved] = useState(false);
  const [target, setTarget] = useState<DLQItem | null>(null);
  const [action, setAction] = useState<"resolve" | "requeue">("resolve");

  const { data, isLoading, refetch } = useDLQ({ resolved: showResolved, limit: 50 });
  const resolveMut = useResolveDLQ();
  const requeueMut = useRequeueDLQ();

  const handleConfirm = async () => {
    if (!target) return;
    try {
      if (action === "resolve") {
        await resolveMut.mutateAsync({ id: target.id, notes: "手動標記為已解決" });
        toast.success(`DLQ #${target.id} 已標記為已解決`);
      } else {
        await requeueMut.mutateAsync(target.id);
        toast.success(`DLQ #${target.id} 已重新派發`);
      }
      setTarget(null);
    } catch (e) {
      toast.error(`操作失敗:${(e as Error).message}`);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="資料管線管理"
        description="Celery Dead Letter Queue 與資料來源同步狀態"
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowResolved(!showResolved)}
            >
              {showResolved ? "只看未解決" : "顯示已解決"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="mr-1 h-4 w-4" />
              重新整理
            </Button>
          </div>
        }
      />

      {/* Source last success — 後端尚未提供,先顯示 placeholder */}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { name: "TWSE OHLCV", task: "sync_ohlcv_tw" },
          { name: "US Yahoo OHLCV", task: "sync_ohlcv_us" },
          { name: "News Ingest", task: "news_ingest" },
        ].map((s) => (
          <Card key={s.task}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-sm">
                {s.name}
                <CheckCircle2 className="h-4 w-4 text-success" />
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">最後成功時間需 P19/P20 整合</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                disabled
                title="v1.1 開放手動觸發"
              >
                觸發(v1.1)
              </Button>
            </CardContent>
          </Card>
        ))}
      </section>

      {/* DLQ list */}
      <section className="space-y-2">
        <h3 className="text-sm font-medium">
          Dead Letter Queue ({showResolved ? "已解決" : "未解決"})
        </h3>
        {isLoading ? (
          <LoadingSkeleton rows={4} />
        ) : !data || data.length === 0 ? (
          <EmptyState
            title={showResolved ? "尚無已解決 DLQ" : "DLQ 為空,系統健康"}
          />
        ) : (
          <div className="space-y-2">
            {data.map((row) => (
              <div
                key={row.id}
                className="rounded-lg border bg-card p-3 text-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                    <div>
                      <p className="font-mono text-xs text-muted-foreground">
                        #{row.id} · {row.task_name} · {row.retry_count} retries
                      </p>
                      <p className="mt-1 font-medium">
                        {row.exception_type ?? "Unknown"}: {row.exception ?? "-"}
                      </p>
                      <p className="text-xs text-muted-foreground tabular-nums">
                        {row.failed_at}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {!row.resolved ? (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setAction("requeue");
                            setTarget(row);
                          }}
                        >
                          重新派發
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setAction("resolve");
                            setTarget(row);
                          }}
                        >
                          標記已解決
                        </Button>
                      </>
                    ) : (
                      <span className="text-xs text-success">
                        已解決 {row.resolved_at?.slice(0, 16)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Confirm dialog,顯示原始 traceback(PLAN 強調不要藏) */}
      <ConfirmDialog
        open={Boolean(target)}
        onOpenChange={(o) => {
          if (!o) setTarget(null);
        }}
        title={action === "resolve" ? "標記為已解決?" : "重新派發任務?"}
        description={
          target ? (
            <span className="whitespace-pre-wrap font-mono text-xs">
              {`任務:${target.task_name}\n錯誤:${target.exception ?? "-"}\n失敗時間:${target.failed_at}`}
            </span>
          ) : null
        }
        onConfirm={handleConfirm}
        confirmLabel={action === "resolve" ? "標記已解決" : "重新派發"}
        loading={resolveMut.isPending || requeueMut.isPending}
      />
    </div>
  );
}

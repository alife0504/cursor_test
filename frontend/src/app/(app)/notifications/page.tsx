"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useNotificationLogs,
  useNotificationSettings,
  useSendTestNotification,
  useUpdateNotificationSettings,
} from "@/hooks/useNotifications";

// Phase 17 § N:通知設定
//   - PLAN 已知陷阱:後端只回 line_token_masked,前端不去 GET 真值;
//     寫入時 line_token 為新值,空字串清空,None 不變(對齊 backend schema)
//   - 訂閱事件 checkbox
//   - 測試發送按鈕
//   - 通知歷史 log cursor pagination

const EVENT_OPTIONS = [
  { value: "analysis.completed", label: "分析完成" },
  { value: "analysis.failed", label: "分析失敗" },
  { value: "order.approved", label: "訂單核准" },
  { value: "order.rejected", label: "訂單拒絕" },
  { value: "system.alert", label: "系統警告" },
];

export default function NotificationsPage() {
  const settings = useNotificationSettings();
  const updateMut = useUpdateNotificationSettings();
  const testMut = useSendTestNotification();

  const [lineToken, setLineToken] = useState<string>("");
  const [chatId, setChatId] = useState<string>("");
  const [events, setEvents] = useState<string[]>([]);
  const [emailEnabled, setEmailEnabled] = useState<boolean>(false);
  const [qhStart, setQhStart] = useState<string>("");
  const [qhEnd, setQhEnd] = useState<string>("");

  useEffect(() => {
    if (settings.data) {
      setChatId(settings.data.telegram_chat_id ?? "");
      setEvents(settings.data.enabled_events ?? []);
      setEmailEnabled(settings.data.email_enabled);
      setQhStart(settings.data.quiet_hours_start ?? "");
      setQhEnd(settings.data.quiet_hours_end ?? "");
    }
  }, [settings.data]);

  const toggleEvent = (ev: string) => {
    setEvents((prev) =>
      prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev],
    );
  };

  const handleSave = async () => {
    try {
      await updateMut.mutateAsync({
        // 空字串 = 不更新 token(避免 PUT 把使用者已存的 token 清掉)
        line_token: lineToken === "" ? null : lineToken,
        telegram_chat_id: chatId === "" ? null : chatId,
        email_enabled: emailEnabled,
        enabled_events: events,
        quiet_hours_start: qhStart || null,
        quiet_hours_end: qhEnd || null,
      });
      setLineToken("");
      toast.success("通知設定已儲存");
    } catch (e) {
      toast.error(`儲存失敗:${(e as Error).message}`);
    }
  };

  const handleTest = async (channel: "line" | "telegram") => {
    try {
      await testMut.mutateAsync({
        channel,
        message: `TradingAgents-TW 測試通知(${channel})`,
      });
      toast.success(`已送出測試通知到 ${channel}`);
    } catch (e) {
      toast.error(`測試發送失敗:${(e as Error).message}`);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="通知設定"
        description="LINE Notify / Telegram 通知與訂閱事件"
      />

      {settings.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <section className="grid gap-4 rounded-lg border bg-card p-4">
          <h3 className="text-sm font-medium">頻道設定</h3>

          {/* LINE token */}
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <div className="flex flex-col gap-1">
              <Label htmlFor="line-token" className="text-xs">
                LINE Notify Token
                {settings.data?.line_token_masked ? (
                  <span className="ml-2 text-xs text-success">
                    （已設定：{settings.data.line_token_masked}）
                  </span>
                ) : (
                  <span className="ml-2 text-xs text-muted-foreground">
                    (尚未設定)
                  </span>
                )}
              </Label>
              <Input
                id="line-token"
                value={lineToken}
                onChange={(e) => setLineToken(e.target.value)}
                placeholder="輸入新 token 以更新,留空不變"
                type="password"
              />
            </div>
            <Button
              variant="outline"
              onClick={() => handleTest("line")}
              disabled={testMut.isPending || !settings.data?.line_token_masked}
            >
              測試 LINE
            </Button>
          </div>

          {/* Telegram chat id */}
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <div className="flex flex-col gap-1">
              <Label htmlFor="tg-chat-id" className="text-xs">Telegram chat_id</Label>
              <Input
                id="tg-chat-id"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                placeholder="例:-100123456789"
              />
            </div>
            <Button
              variant="outline"
              onClick={() => handleTest("telegram")}
              disabled={testMut.isPending || !chatId}
            >
              測試 Telegram
            </Button>
          </div>

          {/* Email enabled */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="email-enabled"
              checked={emailEnabled}
              onCheckedChange={(c) => setEmailEnabled(Boolean(c))}
            />
            <Label htmlFor="email-enabled" className="text-sm">
              啟用 Email 通知
            </Label>
          </div>

          {/* Quiet hours */}
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="flex flex-col gap-1">
              <Label htmlFor="qh-start" className="text-xs">勿擾起(HH:MM)</Label>
              <Input
                id="qh-start"
                value={qhStart}
                onChange={(e) => setQhStart(e.target.value)}
                placeholder="22:00"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="qh-end" className="text-xs">勿擾迄(HH:MM)</Label>
              <Input
                id="qh-end"
                value={qhEnd}
                onChange={(e) => setQhEnd(e.target.value)}
                placeholder="07:00"
              />
            </div>
          </div>
        </section>
      )}

      {/* Events */}
      <section className="grid gap-3 rounded-lg border bg-card p-4">
        <h3 className="text-sm font-medium">訂閱事件</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          {EVENT_OPTIONS.map((ev) => (
            <label
              key={ev.value}
              className="flex items-center gap-2 rounded-md border p-2 hover:bg-accent"
            >
              <Checkbox
                checked={events.includes(ev.value)}
                onCheckedChange={() => toggleEvent(ev.value)}
              />
              <span className="text-sm">{ev.label}</span>
              <code className="ml-auto text-xs text-muted-foreground">{ev.value}</code>
            </label>
          ))}
        </div>
      </section>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={updateMut.isPending}>
          {updateMut.isPending ? "儲存中..." : "儲存設定"}
        </Button>
      </div>

      {/* History */}
      <NotificationLogsTable />
    </div>
  );
}

function NotificationLogsTable() {
  const [cursor, setCursor] = useState<string | null>(null);
  const [stack, setStack] = useState<(string | null)[]>([]);
  const { data, isLoading } = useNotificationLogs({ cursor });

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-sm font-medium">最近通知</h3>
      {isLoading ? (
        <LoadingSkeleton rows={3} />
      ) : !data || data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">尚無通知記錄</p>
      ) : (
        <div className="rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-2">時間</th>
                <th className="p-2">頻道</th>
                <th className="p-2">事件</th>
                <th className="p-2">狀態</th>
                <th className="p-2">錯誤</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((log) => (
                <tr key={log.id} className="border-b">
                  <td className="p-2 text-xs tabular-nums">
                    {log.sent_at?.slice(0, 16)}
                  </td>
                  <td className="p-2 font-mono text-xs">{log.channel}</td>
                  <td className="p-2 text-xs text-muted-foreground">{log.event_type}</td>
                  <td
                    className={`p-2 text-xs font-medium ${
                      log.status === "sent" || log.status === "success"
                        ? "text-success"
                        : "text-destructive"
                    }`}
                  >
                    {log.status}
                  </td>
                  <td className="p-2 text-xs text-muted-foreground">
                    {log.error_msg ?? "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination
        hasMore={data?.hasMore ?? false}
        onNext={() => {
          if (data?.nextCursor) {
            setStack((s) => [...s, cursor]);
            setCursor(data.nextCursor);
          }
        }}
        onPrev={() => {
          const prev = stack[stack.length - 1] ?? null;
          setStack((s) => s.slice(0, -1));
          setCursor(prev);
        }}
        canGoBack={stack.length > 0}
      />
    </section>
  );
}

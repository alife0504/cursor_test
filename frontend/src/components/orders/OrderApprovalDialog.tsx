"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApproveOrder, useRejectOrder } from "@/hooks/useOrders";
import type { OrderSummary } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface ApprovalDialogProps {
  order: OrderSummary | null;
  mode: "approve" | "reject" | null;
  onClose: () => void;
}

// 訂單核准 / 拒絕：
//   - 雙重確認：(1) 視覺資訊卡 (2) 勾選確認框 + 二次按鈕
//   - 並發保護：409 → toast「已被處理」並關閉
//   - 紅綠 token：BUY=signal-buy（紅）/ SELL=signal-sell（綠）
export function OrderApprovalDialog({
  order,
  mode,
  onClose,
}: ApprovalDialogProps) {
  const [confirmed, setConfirmed] = useState(false);
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  const approve = useApproveOrder();
  const reject = useRejectOrder();

  const reset = () => {
    setConfirmed(false);
    setNotes("");
    setReason("");
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const isApprove = mode === "approve";
  const pending = approve.isPending || reject.isPending;

  const submit = async () => {
    if (!order || !mode) return;
    try {
      if (mode === "approve") {
        await approve.mutateAsync({
          id: order.id,
          notes: notes || null,
          expectedVersion: order.version,
        });
        toast.success("已核准訂單");
      } else {
        if (!reason.trim()) {
          toast.error("請填寫拒絕原因");
          return;
        }
        await reject.mutateAsync({
          id: order.id,
          reason,
          expectedVersion: order.version,
        });
        toast.success("已拒絕訂單");
      }
      handleClose();
    } catch (e) {
      const err = e as Error & { response?: { status?: number } };
      const status = err.response?.status;
      if (status === 409) {
        toast.error("此訂單已被處理，列表將自動更新");
      } else {
        toast.error(err.message || "操作失敗");
      }
      handleClose();
    }
  };

  if (!order || !mode) return null;

  const isBuy = order.side === "BUY";

  return (
    <Dialog open={!!order && !!mode} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            {isApprove ? "核准訂單（雙重確認）" : "拒絕訂單"}
          </DialogTitle>
          <DialogDescription>
            {isApprove
              ? "操作不可復原。請仔細核對下方欄位後勾選確認框，再按「確認核准」。"
              : "拒絕後狀態將變為 REJECTED，無法復原。"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 rounded-lg border bg-muted/30 p-3 text-sm">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <div className="text-xs text-muted-foreground">代號</div>
              <div className="font-mono font-semibold">{order.symbol}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">方向</div>
              <div
                data-side={order.side}
                className={cn(
                  "font-semibold",
                  isBuy ? "text-signal-buy" : "text-signal-sell",
                )}
              >
                {isBuy ? "買進（BUY）" : "賣出（SELL）"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">數量</div>
              <div className="num font-semibold">{order.qty}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">目標價</div>
              <div className="num font-semibold">
                {order.target_price ?? "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">停損</div>
              <div className="num font-semibold text-bear">
                {order.stop_loss ?? "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">停利</div>
              <div className="num font-semibold text-bull">
                {order.take_profit ?? "—"}
              </div>
            </div>
          </div>
        </div>

        {isApprove ? (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="ord-note">備註（可選，會記錄到 audit log）</Label>
              <Input
                id="ord-note"
                value={notes}
                maxLength={500}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="例如：依分析建議執行"
              />
            </div>
            <label className="flex items-start gap-2 rounded-md border bg-muted/30 p-3 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>
                我已核對代號、方向、數量與止損/止盈，
                <strong>同意送出核准</strong>
              </span>
            </label>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Label htmlFor="ord-reason">拒絕原因（必填）</Label>
            <Input
              id="ord-reason"
              value={reason}
              maxLength={500}
              onChange={(e) => setReason(e.target.value)}
              placeholder="例如：訊號信心不足 / 不符風控規則"
            />
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={pending}>
            取消
          </Button>
          <Button
            variant={isApprove ? "default" : "destructive"}
            onClick={() => void submit()}
            disabled={pending || (isApprove ? !confirmed : !reason.trim())}
          >
            {pending ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : null}
            {pending
              ? "處理中..."
              : isApprove
                ? "確認核准"
                : "確認拒絕"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

"use client";

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

// Phase 16 § H:訂單核准 / 拒絕
//   - 雙重確認:step 1 顯示資訊 + 確認框
//                step 2 必須勾「我已確認」+ 二次點擊
//   - 並發保護:接 409 → toast「已被其他人處理」並關閉
export function OrderApprovalDialog({ order, mode, onClose }: ApprovalDialogProps) {
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
        toast.error("此訂單已被其他人處理,列表將自動更新");
      } else {
        toast.error(err.message || "操作失敗");
      }
      handleClose();
    }
  };

  if (!order || !mode) return null;

  return (
    <Dialog open={!!order && !!mode} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isApprove ? "核准訂單(雙重確認)" : "拒絕訂單"}
          </DialogTitle>
          <DialogDescription>
            {isApprove
              ? "操作不可復原,請仔細核對訂單內容後勾選確認框,再按確認"
              : "拒絕後該訂單狀態變為 REJECTED,不可復原"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 rounded-md bg-muted/40 p-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-xs text-muted-foreground">代號</div>
              <div className="font-medium">{order.symbol}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">方向</div>
              <div
                className={cn(
                  "font-medium",
                  order.side === "BUY" ? "text-emerald-600" : "text-rose-600",
                )}
              >
                {order.side}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">數量</div>
              <div className="font-medium tabular-nums">{order.qty}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">目標價</div>
              <div className="font-medium tabular-nums">
                {order.target_price ?? "-"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">止損</div>
              <div className="font-medium tabular-nums">
                {order.stop_loss ?? "-"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">止盈</div>
              <div className="font-medium tabular-nums">
                {order.take_profit ?? "-"}
              </div>
            </div>
          </div>
        </div>

        {isApprove ? (
          <div className="space-y-2">
            <div className="space-y-1.5">
              <Label htmlFor="ord-note">備註(可選)</Label>
              <Input
                id="ord-note"
                value={notes}
                maxLength={500}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>
                我已核對代號、方向、數量與止損 / 止盈,
                <strong>同意送出核准</strong>
              </span>
            </label>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Label htmlFor="ord-reason">拒絕原因(必填)</Label>
            <Input
              id="ord-reason"
              value={reason}
              maxLength={500}
              onChange={(e) => setReason(e.target.value)}
              placeholder="例如:訊號信心不足"
            />
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            取消
          </Button>
          <Button
            variant={isApprove ? "default" : "destructive"}
            onClick={() => void submit()}
            disabled={
              pending || (isApprove ? !confirmed : !reason.trim())
            }
          >
            {pending ? "處理中..." : isApprove ? "確認核准" : "確認拒絕"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

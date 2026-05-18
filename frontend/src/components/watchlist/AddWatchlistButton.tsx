"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { StockPicker } from "@/components/common/StockPicker";
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
import { useAddWatchlist } from "@/hooks/useWatchlist";
import type { StockSummary, WatchlistMarket } from "@/lib/api-types";

// Phase 16 § C:加入自選股
function normalizeMarket(m: string): WatchlistMarket {
  const u = (m || "").toUpperCase();
  if (u === "TWSE" || u === "TPEX") return u;
  if (u === "NYSE" || u === "NASDAQ" || u === "AMEX") return u;
  // 後端 stocks.market 可能是 TW / US -> 映射到 TWSE / NYSE 預設
  if (u === "TW") return "TWSE";
  if (u === "US") return "NYSE";
  return "OTHER";
}

export function AddWatchlistButton() {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<StockSummary | null>(null);
  const [note, setNote] = useState("");
  const [tag, setTag] = useState("");
  const add = useAddWatchlist();

  const reset = () => {
    setPicked(null);
    setNote("");
    setTag("");
  };

  const onSubmit = async () => {
    if (!picked) {
      toast.error("請先選擇股票");
      return;
    }
    try {
      await add.mutateAsync({
        symbol: picked.symbol,
        market: normalizeMarket(picked.market),
        tag: tag || null,
        notes: note || null,
      });
      toast.success(`已加入 ${picked.symbol}`);
      reset();
      setOpen(false);
    } catch (e) {
      const msg = (e as Error).message || "加入失敗";
      toast.error(msg.includes("UNIQUE") ? "此股票已在自選清單" : msg);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <Button onClick={() => setOpen(true)} className="gap-1">
        <Plus className="h-4 w-4" /> 加入自選股
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>加入自選股</DialogTitle>
          <DialogDescription>搜尋並選擇股票,再加上備註與分類</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="space-y-1.5">
            <Label>股票</Label>
            <StockPicker
              value={picked?.symbol}
              triggerLabel={picked ? `${picked.symbol} ${picked.name}` : undefined}
              onSelect={setPicked}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wl-tag">分類(可選)</Label>
            <Input
              id="wl-tag"
              value={tag}
              maxLength={50}
              onChange={(e) => setTag(e.target.value)}
              placeholder="例如:長期觀察 / 短線"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wl-note">備註(可選)</Label>
            <Input
              id="wl-note"
              value={note}
              maxLength={1000}
              onChange={(e) => setNote(e.target.value)}
              placeholder="自由文字"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={() => void onSubmit()} disabled={add.isPending}>
            {add.isPending ? "新增中..." : "新增"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

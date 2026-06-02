"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Check, Pencil, Trash2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { ErrorState } from "@/components/common/ErrorState";
import { MarketBadge } from "@/components/common/MarketBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useDeleteWatchlist,
  useUpdateWatchlist,
  useWatchlist,
} from "@/hooks/useWatchlist";
import type { WatchlistItem } from "@/lib/api-types";

// Phase 16 § C:Watchlist 表格
//   - inline edit notes(點 icon → input → enter / blur 存)
//   - 刪除走 ConfirmDialog 雙確認
function NotesCell({ item }: { item: WatchlistItem }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(item.notes ?? "");
  const update = useUpdateWatchlist();

  if (!editing) {
    return (
      <div className="flex items-center gap-2">
        <span className="line-clamp-1 max-w-[18rem]">{item.notes || "—"}</span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="編輯備註"
          onClick={() => setEditing(true)}
        >
          <Pencil className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  const save = async () => {
    try {
      await update.mutateAsync({ id: item.id, body: { notes: value } });
      toast.success("已更新備註");
      setEditing(false);
    } catch (e) {
      toast.error(`更新失敗:${(e as Error).message}`);
    }
  };

  return (
    <div className="flex items-center gap-1">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        maxLength={1000}
        className="h-7 max-w-[16rem]"
        autoFocus
        onKeyDown={(e) => {
          if (e.key === "Enter") void save();
          if (e.key === "Escape") setEditing(false);
        }}
      />
      <Button
        variant="ghost"
        size="icon"
        onClick={() => void save()}
        disabled={update.isPending}
        aria-label="儲存備註"
      >
        <Check className="h-3 w-3" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => {
          setValue(item.notes ?? "");
          setEditing(false);
        }}
        aria-label="取消編輯"
      >
        <X className="h-3 w-3" />
      </Button>
    </div>
  );
}

export function WatchlistTable() {
  const { data, isLoading, error } = useWatchlist();
  const items = data ?? [];
  const del = useDeleteWatchlist();
  const [deleteTarget, setDeleteTarget] = useState<WatchlistItem | null>(null);

  const columns: ColumnDef<WatchlistItem>[] = [
    {
      accessorKey: "symbol",
      header: "代號",
      cell: ({ row }) => (
        <span className="font-medium">{row.original.symbol}</span>
      ),
    },
    {
      accessorKey: "market",
      header: "市場",
      cell: ({ row }) => <MarketBadge market={row.original.market} />,
    },
    {
      accessorKey: "tag",
      header: "分類",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {row.original.tag || "—"}
        </span>
      ),
    },
    {
      accessorKey: "notes",
      header: "備註",
      cell: ({ row }) => <NotesCell item={row.original} />,
    },
    {
      accessorKey: "created_at",
      header: "加入時間",
      cell: ({ row }) => (
        <DateFormat value={row.original.created_at} mode="date" />
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">操作</span>,
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          aria-label={`刪除 ${row.original.symbol}`}
          onClick={() => setDeleteTarget(row.original)}
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      ),
    },
  ];

  if (error) {
    return (
      <ErrorState
        title="自選股載入失敗"
        variant="inline"
        onRetry={() => {
          if (typeof window !== "undefined") window.location.reload();
        }}
        error={error}
      />
    );
  }

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await del.mutateAsync(deleteTarget.id);
      toast.success(`已刪除 ${deleteTarget.symbol}`);
      setDeleteTarget(null);
    } catch (e) {
      toast.error(`刪除失敗:${(e as Error).message}`);
    }
  };

  return (
    <>
      <DataTable
        columns={columns}
        data={items}
        isLoading={isLoading}
        emptyText="尚未加入任何自選股"
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="刪除自選股"
        description={
          deleteTarget
            ? `確定要刪除 ${deleteTarget.symbol} (${deleteTarget.market}) 嗎?`
            : ""
        }
        destructive
        loading={del.isPending}
        onConfirm={doDelete}
      />
    </>
  );
}

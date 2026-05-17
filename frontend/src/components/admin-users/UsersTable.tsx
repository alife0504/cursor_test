"use client";

import { ColumnDef } from "@tanstack/react-table";
import { KeyRound, ShieldOff, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { Pagination } from "@/components/common/Pagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  useDeleteUser,
  useResetUserPassword,
  useUpdateUser,
  useUsers,
} from "@/hooks/useUsers";
import type { AdminUserItem } from "@/lib/api-types";
import { cn } from "@/lib/utils";

const ROLE_STYLE: Record<string, string> = {
  ADMIN: "bg-rose-100 text-rose-900",
  ANALYST: "bg-sky-100 text-sky-900",
  VIEWER: "bg-slate-100 text-slate-700",
};

interface ResetPasswordDialogProps {
  user: AdminUserItem | null;
  onClose: () => void;
}

function ResetPasswordDialog({ user, onClose }: ResetPasswordDialogProps) {
  const [pwd, setPwd] = useState("");
  const reset = useResetUserPassword();

  const submit = async () => {
    if (!user) return;
    if (pwd.length < 12) {
      toast.error("密碼至少 12 字");
      return;
    }
    try {
      await reset.mutateAsync({
        id: user.id,
        new_password: pwd,
        must_change_password: true,
      });
      toast.success(`已重設 ${user.email} 的密碼;該用戶下次登入需改密碼`);
      onClose();
      setPwd("");
    } catch (e) {
      toast.error(`重設失敗:${(e as Error).message}`);
    }
  };

  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>重設密碼</DialogTitle>
          <DialogDescription>
            為 {user?.email} 設一個臨時密碼;該用戶下次登入會被要求改密碼
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="new-pwd">臨時密碼(≥12 字、含大小寫數字符號)</Label>
          <Input
            id="new-pwd"
            type="text"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={() => void submit()} disabled={reset.isPending}>
            {reset.isPending ? "處理中..." : "確認"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function UsersTable() {
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack[cursorStack.length - 1];
  const { data, isLoading, error } = useUsers({ cursor, includeDeleted: true });
  const update = useUpdateUser();
  const del = useDeleteUser();
  const [resetTarget, setResetTarget] = useState<AdminUserItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUserItem | null>(null);

  const items = data?.items ?? [];

  const toggleActive = async (u: AdminUserItem) => {
    try {
      await update.mutateAsync({ id: u.id, is_active: !u.is_active });
      toast.success(u.is_active ? "已停用" : "已啟用");
    } catch (e) {
      toast.error(`更新失敗:${(e as Error).message}`);
    }
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await del.mutateAsync(deleteTarget.id);
      toast.success(`已軟刪除 ${deleteTarget.email}`);
      setDeleteTarget(null);
    } catch (e) {
      toast.error(`刪除失敗:${(e as Error).message}`);
    }
  };

  const columns: ColumnDef<AdminUserItem>[] = [
    {
      accessorKey: "email",
      header: "Email",
      cell: ({ row }) => (
        <div className="flex flex-col">
          <span className="font-medium">{row.original.email}</span>
          <span className="text-xs text-muted-foreground">
            {row.original.full_name || ""}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "role",
      header: "角色",
      cell: ({ row }) => (
        <Badge
          variant="secondary"
          className={cn(ROLE_STYLE[row.original.role] || "")}
        >
          {row.original.role}
        </Badge>
      ),
    },
    {
      accessorKey: "is_active",
      header: "狀態",
      cell: ({ row }) =>
        row.original.is_active ? (
          <Badge
            variant="secondary"
            className="bg-emerald-100 text-emerald-900"
          >
            啟用中
          </Badge>
        ) : (
          <Badge variant="secondary" className="bg-zinc-200 text-zinc-700">
            已停用
          </Badge>
        ),
    },
    {
      accessorKey: "last_login_at",
      header: "上次登入",
      cell: ({ row }) => (
        <DateFormat value={row.original.last_login_at} mode="datetime" />
      ),
    },
    {
      accessorKey: "created_at",
      header: "建立時間",
      cell: ({ row }) => (
        <DateFormat value={row.original.created_at} mode="date" />
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">操作</span>,
      cell: ({ row }) => {
        const u = row.original;
        return (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setResetTarget(u)}
              aria-label="重設密碼"
            >
              <KeyRound className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => void toggleActive(u)}
              aria-label={u.is_active ? "停用" : "啟用"}
              disabled={update.isPending}
            >
              {u.is_active ? (
                <ShieldOff className="h-4 w-4 text-rose-600" />
              ) : (
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
              )}
            </Button>
            {u.is_active ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDeleteTarget(u)}
                className="text-rose-600"
              >
                刪除
              </Button>
            ) : null}
          </div>
        );
      },
    },
  ];

  if (error) {
    return <p className="text-sm text-destructive">用戶列表載入失敗</p>;
  }

  return (
    <>
      <DataTable
        columns={columns}
        data={items}
        isLoading={isLoading}
        emptyText="目前沒有用戶"
      />
      <Pagination
        hasMore={!!data?.hasMore}
        canGoBack={cursorStack.length > 1}
        onPrev={() => setCursorStack((s) => s.slice(0, -1))}
        onNext={() =>
          data?.nextCursor &&
          setCursorStack((s) => [...s, data.nextCursor as string])
        }
      />
      <ResetPasswordDialog
        user={resetTarget}
        onClose={() => setResetTarget(null)}
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="軟刪除用戶"
        description={
          deleteTarget
            ? `確定要停用 ${deleteTarget.email} 嗎?(僅停用,可日後重新啟用)`
            : ""
        }
        destructive
        loading={del.isPending}
        onConfirm={doDelete}
      />
    </>
  );
}

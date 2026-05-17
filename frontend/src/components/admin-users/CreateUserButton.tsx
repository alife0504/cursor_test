"use client";

import { Plus } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateUser } from "@/hooks/useUsers";
import type { UserRole } from "@/lib/api-types";

// Phase 16 § I:admin 新增用戶
//   - email + role + 初始密碼
//   - 強制 must_change_password=true
export function CreateUserButton() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [role, setRole] = useState<UserRole>("VIEWER");
  const [fullName, setFullName] = useState("");
  const create = useCreateUser();

  const reset = () => {
    setEmail("");
    setPwd("");
    setRole("VIEWER");
    setFullName("");
  };

  const submit = async () => {
    if (!email || !pwd) {
      toast.error("Email 與密碼必填");
      return;
    }
    if (pwd.length < 12) {
      toast.error("密碼至少 12 字");
      return;
    }
    try {
      await create.mutateAsync({
        email,
        password: pwd,
        full_name: fullName || null,
        role,
        must_change_password: true,
      });
      toast.success(`已建立 ${email}`);
      reset();
      setOpen(false);
    } catch (e) {
      toast.error(`建立失敗:${(e as Error).message}`);
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
        <Plus className="h-4 w-4" /> 新增用戶
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增用戶</DialogTitle>
          <DialogDescription>
            新用戶下次登入會被強制改密碼
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="cu-email">Email</Label>
            <Input
              id="cu-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cu-name">顯示名稱(可選)</Label>
            <Input
              id="cu-name"
              value={fullName}
              maxLength={100}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cu-role">角色</Label>
            <Select
              value={role}
              onValueChange={(v) => v && setRole(v as UserRole)}
            >
              <SelectTrigger id="cu-role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="VIEWER">VIEWER(唯讀)</SelectItem>
                <SelectItem value="ANALYST">ANALYST(分析師)</SelectItem>
                <SelectItem value="ADMIN">ADMIN(管理者)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cu-pwd">初始密碼</Label>
            <Input
              id="cu-pwd"
              type="text"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              placeholder="≥12 字、大小寫數字符號 4 類"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={() => void submit()} disabled={create.isPending}>
            {create.isPending ? "建立中..." : "建立"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

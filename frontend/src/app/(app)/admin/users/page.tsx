import { CreateUserButton } from "@/components/admin-users/CreateUserButton";
import { UsersTable } from "@/components/admin-users/UsersTable";

// Phase 16 § I:用戶管理(僅 ADMIN)
//   - 後端 /users/* 已用 RBAC 擋,前端 sidebar 對非 admin 隱藏即可
export default function AdminUsersPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">用戶管理</h1>
          <p className="text-sm text-muted-foreground">
            建立 / 啟用停用 / 重設密碼;此頁僅 ADMIN 可看
          </p>
        </div>
        <CreateUserButton />
      </div>
      <UsersTable />
    </div>
  );
}

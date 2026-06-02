import { PageHeader } from "@/components/common/PageHeader";
import { CreateUserButton } from "@/components/admin-users/CreateUserButton";
import { UsersTable } from "@/components/admin-users/UsersTable";

// 用戶管理（僅 ADMIN）
export default function AdminUsersPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="用戶管理"
        description="建立 / 啟用停用 / 重設密碼。此頁僅 ADMIN 可看"
        actions={<CreateUserButton />}
      />
      <UsersTable />
    </div>
  );
}

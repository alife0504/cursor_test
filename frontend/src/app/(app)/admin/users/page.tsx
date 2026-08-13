"use client";

import { ShieldCheck, UserCog, UserCheck, Users } from "lucide-react";
import { useMemo } from "react";

import { CreateUserButton } from "@/components/admin-users/CreateUserButton";
import { UsersTable } from "@/components/admin-users/UsersTable";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { useUsers } from "@/hooks/useUsers";

// 用戶管理（僅 ADMIN）— 頂部摘要 KPI（共用 useUsers 快取，不重複抓）
export default function AdminUsersPage() {
  const { data } = useUsers();
  const items = data?.items ?? [];

  const summary = useMemo(() => {
    const admins = items.filter((u) => u.role === "ADMIN").length;
    const active = items.filter((u) => u.is_active).length;
    const mustChange = items.filter((u) => u.must_change_password).length;
    return { n: items.length, admins, active, mustChange };
  }, [items]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={Users}
        title="用戶管理"
        description="建立 / 啟用停用 / 重設密碼。此頁僅 ADMIN 可看"
        actions={<CreateUserButton />}
      />

      {/* 摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="總用戶"
          value={summary.n}
          subtitle={`啟用中 ${summary.active} 人`}
          icon={Users}
          accent="primary"
        />
        <KpiCard
          title="管理員 ADMIN"
          value={summary.admins}
          subtitle="最高權限帳號"
          icon={ShieldCheck}
          accent="info"
        />
        <KpiCard
          title="啟用中"
          value={summary.active}
          subtitle={`停用 ${summary.n - summary.active} 人`}
          icon={UserCheck}
          accent="info"
        />
        <KpiCard
          title="待改密碼"
          value={summary.mustChange}
          subtitle="首次登入需更換"
          icon={UserCog}
          accent="warning"
        />
      </section>

      <UsersTable />
    </div>
  );
}

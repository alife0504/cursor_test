import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.admin.users")}
      description="用戶管理(僅 ADMIN)"
      plannedPhase="P16"
    />
  );
}

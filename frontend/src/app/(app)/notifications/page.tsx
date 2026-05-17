import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.notifications")}
      description="LINE / Email 通知設定"
      plannedPhase="P17"
    />
  );
}

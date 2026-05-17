import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.admin.system")}
      description="系統監控(Metrics、Health)"
      plannedPhase="P17"
    />
  );
}

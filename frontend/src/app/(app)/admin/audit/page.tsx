import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.admin.audit")}
      description="審計日誌(hash chain 完整性)"
      plannedPhase="P16"
    />
  );
}

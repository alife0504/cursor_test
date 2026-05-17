import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.portfolio.history")}
      description="交易記錄"
      plannedPhase="P17"
    />
  );
}

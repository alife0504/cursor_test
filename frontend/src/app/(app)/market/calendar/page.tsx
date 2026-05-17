import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.market.calendar")}
      description="財報日曆(P17 先 mock,v1.1 接真實資料)"
      plannedPhase="P17"
    />
  );
}

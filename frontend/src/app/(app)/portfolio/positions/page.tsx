import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.portfolio.positions")}
      description="模擬持倉 P&L"
      plannedPhase="P17"
    />
  );
}

import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.statistics.backtest")}
      description="回測結果(P17 mock,v1.1 接真實)"
      plannedPhase="P17"
    />
  );
}

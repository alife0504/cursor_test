import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.statistics.accuracy")}
      description="AI 分析準確率統計"
      plannedPhase="P17"
    />
  );
}

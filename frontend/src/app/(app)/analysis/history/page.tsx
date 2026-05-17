import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.analysis.history")}
      description="歷史分析報告列表"
      plannedPhase="P16"
    />
  );
}

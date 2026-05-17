import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.analysis.new")}
      description="送出新的 AI 多智能體分析任務"
      plannedPhase="P16"
    />
  );
}

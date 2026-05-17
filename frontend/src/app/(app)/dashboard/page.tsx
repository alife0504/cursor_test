import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.dashboard")}
      description="儀表板:今日重點訊號、待辦、市場摘要"
      plannedPhase="P16"
    />
  );
}

import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.screener.filter")}
      description="多條件選股篩選器"
      plannedPhase="P17"
    />
  );
}

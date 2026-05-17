import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.screener.compare")}
      description="多股比較(基本面、技術面、估值)"
      plannedPhase="P17"
    />
  );
}

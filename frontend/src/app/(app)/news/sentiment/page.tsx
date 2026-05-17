import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.news.sentiment")}
      description="新聞情緒分析"
      plannedPhase="P17"
    />
  );
}

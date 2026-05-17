import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.news.announcements")}
      description="重大公告 / 法說會"
      plannedPhase="P17"
    />
  );
}

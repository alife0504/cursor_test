import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.admin.pipeline")}
      description="資料管線狀態 / Celery DLQ / Circuit Breaker"
      plannedPhase="P17"
    />
  );
}

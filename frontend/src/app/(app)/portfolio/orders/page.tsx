import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.portfolio.orders")}
      description="待核准訂單(P14 後端 signal → pending_order)"
      plannedPhase="P16"
    />
  );
}

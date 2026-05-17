import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.market.institutional")}
      description="三大法人買賣超(僅台股)"
      plannedPhase="P17"
    />
  );
}

import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.screener.watchlist")}
      description="自選股清單,即時行情 + 訊號"
      plannedPhase="P16"
    />
  );
}

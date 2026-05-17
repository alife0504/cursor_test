import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.market.overview")}
      description="台股 / 美股大盤指數、產業類股漲跌"
      plannedPhase="P17"
    />
  );
}

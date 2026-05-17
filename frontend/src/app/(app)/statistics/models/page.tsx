import { PageStub } from "@/components/common/PageStub";
import { t } from "@/i18n/messages";

export default function Page() {
  return (
    <PageStub
      title={t("nav.statistics.models")}
      description="模型比較(Gemini / OpenAI / Anthropic)"
      plannedPhase="P17"
    />
  );
}

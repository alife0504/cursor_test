import { PageStub } from "@/components/common/PageStub";

interface PageProps {
  params: { id: string };
}

export default function Page({ params }: PageProps) {
  return (
    <PageStub
      title="辯論詳情"
      description={`分析 ID:${params.id}(WS 串流 Bull / Bear 辯論)`}
      plannedPhase="P16"
    />
  );
}

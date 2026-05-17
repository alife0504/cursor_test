import { Wrench } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n/messages";

interface PageStubProps {
  title: string;
  description?: string;
  /** 標註此頁將在哪個 Phase 完整實作(例:P16 / P17) */
  plannedPhase?: string;
}

// 18 頁路由空殼共用組件,真正內容由 P16 / P17 補完
export function PageStub({ title, description, plannedPhase }: PageStubProps) {
  return (
    <div className="flex h-full w-full flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Wrench className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>{t("page.stub.title")}</CardTitle>
              <CardDescription>{t("page.stub.desc")}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {plannedPhase
              ? `預計實作 Phase:${plannedPhase}`
              : "預計實作 Phase:P16 / P17"}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { t } from "@/i18n/messages";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function OnboardingPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const onContinue = async () => {
    setSubmitting(true);
    try {
      // 後端持久化 onboarding_completed=true（此端點必須存在，否則 AuthBootstrap 守衛會把
      // 使用者無限彈回 /onboarding）。成功後樂觀更新 store，避免導頁時守衛用陳舊 false 誤判。
      await api.post("/users/me/onboarding-complete");
      if (user) setUser({ ...user, onboarding_completed: true });
      router.replace("/dashboard");
    } catch {
      toast.error(t("common.error"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>{t("onboarding.welcome.title")}</CardTitle>
            <CardDescription>{t("onboarding.welcome.desc")}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <Section
          title="1. 建立自選股清單"
          body="從台股 / 美股股票庫中挑選你關注的標的,系統會自動為你推送每日資訊。"
        />
        <Section
          title="2. 啟動第一個 AI 分析"
          body="選定股票後,送出多智能體分析任務。Bull / Bear 兩位分析師會展開辯論,結論交由 Manager 收斂。"
        />
        <Section
          title="3. 等待 Discord / Email 通知"
          body="分析完成、重大訊號出現或訂單待核准時,系統會主動通知你。"
        />
      </CardContent>
      <CardFooter>
        <Button onClick={onContinue} className="w-full" disabled={submitting}>
          {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {t("onboarding.welcome.cta")}
        </Button>
      </CardFooter>
    </Card>
  );
}

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-muted-foreground">{body}</p>
    </div>
  );
}

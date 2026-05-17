"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n/messages";
import { api } from "@/lib/api";

const passwordRule = z
  .string()
  .min(12, "至少 12 字元")
  .regex(/[A-Z]/, "需含大寫")
  .regex(/[a-z]/, "需含小寫")
  .regex(/\d/, "需含數字")
  .regex(/[^A-Za-z0-9]/, "需含特殊符號");

const schema = z
  .object({
    new_password: passwordRule,
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "兩次密碼不一致",
    path: ["confirm_password"],
  });

type Values = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordPageInner />
    </Suspense>
  );
}

function ResetPasswordPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const onSubmit = async (values: Values) => {
    if (!token) {
      toast.error("缺少重置 token");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/auth/password-reset/confirm", {
        token,
        new_password: values.new_password,
      });
      toast.success(t("auth.reset.success"));
      router.replace("/login");
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 400) {
        toast.error("重置連結已失效,請重新申請");
      } else {
        toast.error(t("common.error"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth.reset.title")}</CardTitle>
        <CardDescription>{t("onboarding.change_pw.rules")}</CardDescription>
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <CardContent className="flex flex-col gap-4">
            {!token && (
              <p className="text-sm text-destructive">
                連結無效,請從信件中重新點擊
              </p>
            )}
            <FormField
              control={form.control}
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.reset.new_password")}</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoComplete="new-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirm_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.reset.confirm_password")}</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoComplete="new-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button
              type="submit"
              className="w-full"
              disabled={submitting || !token}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("auth.reset.submit")}
            </Button>
            <Link
              href="/login"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ← 返回登入
            </Link>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}

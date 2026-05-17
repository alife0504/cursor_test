"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
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

const schema = z.object({
  email: z.string().email("請輸入有效的 email"),
});

type Values = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  const onSubmit = async (values: Values) => {
    setSubmitting(true);
    try {
      // 後端永遠 200(避免帳號探測),前端統一顯示「若該 email 已註冊」
      await api.post("/auth/password-reset", values);
      setSent(true);
      toast.success(t("auth.forgot.success"));
    } catch {
      // 429 rate limit 等錯誤,還是顯示一致訊息
      setSent(true);
      toast.success(t("auth.forgot.success"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth.forgot.title")}</CardTitle>
        <CardDescription>
          請輸入註冊時使用的 email,系統會寄送重置連結
        </CardDescription>
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <CardContent className="flex flex-col gap-4">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.login.email")}</FormLabel>
                  <FormControl>
                    <Input type="email" placeholder="you@example.com" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {sent && (
              <p className="text-sm text-muted-foreground">
                {t("auth.forgot.success")}
              </p>
            )}
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button
              type="submit"
              className="w-full"
              disabled={submitting || sent}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("auth.forgot.submit")}
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

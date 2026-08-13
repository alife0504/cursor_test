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
import { api, type ApiEnvelope } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

const loginSchema = z.object({
  email: z.string().email("請輸入有效的 email"),
  password: z.string().min(1, "請輸入密碼"),
});

type LoginValues = z.infer<typeof loginSchema>;

type NextAction = "change_password" | "onboarding" | "dashboard";

interface LoginResponseData {
  access_token: string;
  expires_in: number;
  next_action: NextAction;
  user: {
    id: string;
    email: string;
    role: "ADMIN" | "ANALYST" | "VIEWER";
    must_change_password?: boolean;
    onboarding_completed?: boolean;
    preferred_timezone?: string;
  };
}

function resolveNextRoute(action: NextAction, fallback: string | null): string {
  if (action === "change_password") return "/onboarding/change-password";
  if (action === "onboarding") return "/onboarding";
  return fallback || "/dashboard";
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageInner />
    </Suspense>
  );
}

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");
  const [submitting, setSubmitting] = useState(false);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (values: LoginValues) => {
    setSubmitting(true);
    try {
      const res = await api.post<ApiEnvelope<LoginResponseData>>(
        "/auth/login",
        values,
      );
      const data = res.data?.data;
      if (!data?.access_token) {
        throw new Error("login response missing access_token");
      }
      setAccessToken(data.access_token);
      setUser(data.user);
      const target = resolveNextRoute(data.next_action, next);
      router.replace(target);
    } catch (err) {
      if (isAxiosError(err)) {
        const code = err.response?.status;
        if (code === 401 || code === 422) {
          toast.error(t("auth.login.error.invalid"));
        } else if (code === 423 || code === 429) {
          toast.error(t("auth.login.error.locked"));
        } else {
          toast.error(t("auth.login.error.generic"));
        }
      } else {
        toast.error(t("auth.login.error.generic"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth.login.title")}</CardTitle>
        <CardDescription>{t("app.tagline")}</CardDescription>
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <CardContent className="flex flex-col gap-4">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.login.email")}</FormLabel>
                  <FormControl>
                    <Input
                      type="email"
                      autoComplete="email"
                      placeholder="you@example.com"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.login.password")}</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoComplete="current-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("auth.login.submit")}
            </Button>
            <Link
              href="/forgot-password"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t("auth.login.forgot")}
            </Link>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}

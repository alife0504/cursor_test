"use client";

import { useEffect, useState } from "react";

// 台股平台一律以台北時間為準。
const TW_TIMEZONE = "Asia/Taipei";

function taipeiDateString(now: Date): string {
  return now.toLocaleDateString("zh-TW", {
    timeZone: TW_TIMEZONE,
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

function taipeiHour(now: Date): number {
  // hourCycle h23 → "00"~"23"（避免 hour12:false 在部分環境把午夜給成 "24"）
  return Number(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: TW_TIMEZONE,
      hour: "2-digit",
      hourCycle: "h23",
    }).format(now),
  );
}

function greetingFor(h: number): string {
  if (h < 5) return "夜深了";
  if (h < 11) return "早安";
  if (h < 14) return "午安";
  if (h < 18) return "午後好";
  return "晚安";
}

/**
 * 儀表板的「時段問候 + 今日日期」。
 *
 * ⚠️ 為什麼一定要是 Client Component：
 * 原本這段寫在 dashboard 的 Server Component 裡直接呼叫 new Date()。Next.js App Router
 * 對「沒用到動態 API」的頁面預設會在 **build 時預渲染並永久快取** → new Date() 被烤死在
 * 打包那一刻，使用者每次開啟看到的都是「建置日」而非今天（實測建置於 7/21 23:11，隔天
 * 7/22 開啟仍顯示「2026年7月21日星期二」，差一整天）。
 *
 * 改在瀏覽器端計算可徹底免疫任何快取層（build cache / CDN / proxy），並且每分鐘重算一次，
 * 讓長時間掛著的頁面在跨午夜、跨時段（早安→午安）時也會自己更新。
 * 首次渲染回 null（server 與 client 一致）以避免 hydration 不一致警告。
 */
export function TodayGreeting({ suffix }: { suffix?: string }) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    // 每分鐘重算：跨午夜換日、跨時段換問候語都會自動反映
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  if (now === null) {
    // SSR / hydration 前的佔位：保留行高避免版面跳動
    return <span className="opacity-0">—</span>;
  }
  return (
    <>
      {greetingFor(taipeiHour(now))}
      {suffix ?? ""}
    </>
  );
}

/** 儀表板副標的「今日 YYYY年M月D日星期X」。同上，必須在瀏覽器端算。 */
export function TodayDate() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  if (now === null) return <span className="opacity-0">—</span>;
  return <>{taipeiDateString(now)}</>;
}

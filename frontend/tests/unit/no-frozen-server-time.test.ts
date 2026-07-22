import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

/**
 * 回歸守門：禁止「Server Component 直接算當下時間」。
 *
 * 事故（2026-07-22）：dashboard/page.tsx 是 Server Component 又直接呼叫 new Date()。
 * Next.js App Router 對「沒用到動態 API」的頁面預設會在 **build 時預渲染並永久快取**，
 * 於是那個時間被求值在 docker build 當下、烤進 HTML → 使用者每次開啟看到的都是建置日。
 * 實測建置於 7/21 23:11，隔天 7/22 開啟仍顯示「2026年7月21日星期二」，整整差一天。
 * 這類錯誤不會拋例外、不會被 tsc/ESLint 抓到，只會靜靜顯示錯的日期。
 *
 * 規則：page.tsx / layout.tsx 若**不是** client component，就不得出現取得當下時間的呼叫
 * （new Date() / Date.now()），除非該檔明確宣告 `export const dynamic = "force-dynamic"`。
 * 最佳解仍是把時間顯示放進 Client Component（免疫所有快取層、還能自己跨午夜換日）。
 */

const APP_DIR = path.resolve(__dirname, "../../src/app");

function collectRouteFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...collectRouteFiles(full));
    } else if (/^(page|layout)\.tsx$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

/** 移除註解與字串，避免把說明文字裡的 new Date() 誤判成真的呼叫。 */
function stripCommentsAndStrings(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "") // 區塊註解
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1") // 行註解（避開 http://）
    .replace(/`(?:\\[\s\S]|[^\\`])*`/g, "``") // 樣板字串
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/'(?:\\.|[^'\\])*'/g, "''");
}

const NOW_CALL = /\bnew\s+Date\s*\(\s*\)|\bDate\s*\.\s*now\s*\(/;

describe("Server Component 不得凍結當下時間（build 時預渲染會把時間烤死）", () => {
  const files = collectRouteFiles(APP_DIR);

  it("找得到 app router 檔案（避免路徑改動導致此測試靜默失效）", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    const rel = path.relative(path.resolve(__dirname, "../.."), file);
    it(`${rel} 未在 server 端計算當下時間`, () => {
      const raw = readFileSync(file, "utf8");
      const code = stripCommentsAndStrings(raw);

      const isClient = /^\s*["']use client["']/m.test(raw);
      if (isClient) return; // client 端計算永遠是使用者當下時間，安全

      const usesNow = NOW_CALL.test(code);
      if (!usesNow) return;

      // 有用到當下時間 → 必須明確宣告動態渲染，否則會被靜態化並凍結
      const isForcedDynamic =
        /export\s+const\s+dynamic\s*=\s*["']force-dynamic["']/.test(code);
      expect(
        isForcedDynamic,
        `${rel} 是 Server Component 且使用了 new Date()/Date.now()，` +
          `會在 build 時被預渲染而把時間凍在打包那一刻。` +
          `請改用 Client Component 顯示時間（建議），或明確宣告 ` +
          `export const dynamic = "force-dynamic"。`,
      ).toBe(true);
    });
  }
});

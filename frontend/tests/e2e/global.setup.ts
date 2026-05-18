import { expect, test as setup } from "@playwright/test";
import path from "node:path";

// Playwright 推薦 pattern:一次 login,把 cookie 存到 storageState 檔案,
// 後續所有需登入的 test project 用 `storageState: path` 載入,避開 backend
// rate limit(L2 = 5/min/IP)。
//
// 對應 PLAN § 19.3 多層 rate limit:
//   L1 300/min/IP / L2 login 5/min/IP / L3 password-reset 3/hr/IP
// 之前 23 個 spec 每個都打 /auth/login → 第 6 個就 429。

export const ADMIN_AUTH_FILE = path.join(__dirname, ".auth/admin.json");

setup("authenticate as admin", async ({ page }) => {
  const email = process.env.E2E_ADMIN_EMAIL || "admin@example.com";
  const pwd = process.env.E2E_ADMIN_PWD || "AdminInit#2026!";

  const r = await page.context().request.post("/api/v1/auth/login", {
    data: { email, password: pwd },
    failOnStatusCode: false,
  });
  expect(r.ok(), `login failed: ${r.status()} ${await r.text()}`).toBeTruthy();

  // 把 cookies + localStorage 寫到 storageState
  await page.context().storageState({ path: ADMIN_AUTH_FILE });
});

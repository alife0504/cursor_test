import { expect, test } from "@playwright/test";

// 強制未登入狀態(覆寫 globalSetup 的 admin storageState)
test.use({ storageState: { cookies: [], origins: [] } });

// Phase 15 § X:Auth 流程 smoke
// 預先條件:
//   - frontend dev server 在 http://localhost:3000
//   - backend 在 http://localhost:8000(透過 next.config rewrites Proxy)
//   - .env 有 ADMIN_EMAIL / ADMIN_INITIAL_PASSWORD

const adminEmail = process.env.E2E_ADMIN_EMAIL || "admin@example.com";
const adminPwd = process.env.E2E_ADMIN_PWD || "AdminInit#2026!";

test.describe("Auth flow", () => {
  test("未登入訪問 /dashboard → 重導到 /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
    // shadcn nova CardTitle 是 <div data-slot="card-title">,不是 heading
    await expect(page.getByRole("button", { name: "登入" })).toBeVisible();
    await expect(page.getByLabel("電子郵件")).toBeVisible();
  });

  test("錯密碼顯示錯誤訊息", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("電子郵件").fill(adminEmail);
    await page.getByLabel("密碼").fill("totally-wrong-pwd");
    await page.getByRole("button", { name: "登入" }).click();
    // sonner toast 顯示在右上,文字「電子郵件或密碼錯誤」
    await expect(page.getByText(/電子郵件或密碼錯誤|登入失敗/)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("正確登入 → 依 next_action 跳轉", async ({ page }) => {
    test.skip(
      !adminPwd,
      "需要 E2E_ADMIN_PWD or .env 提供 ADMIN_INITIAL_PASSWORD",
    );
    await page.goto("/login");
    await page.getByLabel("電子郵件").fill(adminEmail);
    await page.getByLabel("密碼").fill(adminPwd);
    await page.getByRole("button", { name: "登入" }).click();

    // 第一次登入 next_action=change_password 會跳 /onboarding/change-password
    // 已完成 onboarding 後則是 /dashboard
    await page.waitForURL(
      /\/(onboarding\/change-password|onboarding|dashboard)/,
      { timeout: 15_000 },
    );
    expect(page.url()).toMatch(
      /\/(onboarding\/change-password|onboarding|dashboard)/,
    );
  });
});

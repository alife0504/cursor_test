import { expect, test } from "@playwright/test";

// 此 spec 同時測「已登入 auth-route 重導」與「未登入 protected route 重導」。
// 預設 storageState 是 admin(登入),後面三個 test 用 test.use 覆寫成未登入。

test.describe("Middleware:已登入 auth-route 重導", () => {
  test("已登入訪問 /login → 重導 /dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.waitForURL(/\/dashboard/, { timeout: 5000 });
  });

  test("已登入訪問 /forgot-password → 重導 /dashboard", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.waitForURL(/\/dashboard/, { timeout: 5000 });
  });

  test("已登入訪問 /reset-password?token=x → 重導 /dashboard", async ({
    page,
  }) => {
    await page.goto("/reset-password?token=abc");
    await page.waitForURL(/\/dashboard/, { timeout: 5000 });
  });
});

test.describe("Middleware:未登入 protected route 重導", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("未登入訪問 /portfolio/orders → 重導 /login?next=...", async ({
    page,
  }) => {
    await page.goto("/portfolio/orders");
    await expect(page).toHaveURL(/\/login.*next=.*portfolio.*orders/);
  });

  test("未登入訪問 /admin/users → 重導 /login?next=...", async ({ page }) => {
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/login.*next=.*admin.*users/);
  });
});

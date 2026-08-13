import { expect, test } from "@playwright/test";

// storageState 由 globalSetup 預載入(admin 已登入),不需要在每個 test 再 login

test.describe("Logout flow", () => {
  test("登入後從 Topbar 登出 → cookie 清掉 → 訪問 /dashboard 重導 /login", async ({
    page,
  }) => {
    // 確認登入狀態:能進 /dashboard
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);

    // 開 Topbar 下拉(trigger 含 admin email / 帳號)
    const trigger = page
      .getByRole("button")
      .filter({ hasText: /admin|帳號/i })
      .first();
    await trigger.click();
    // base-ui Menu 不一定用 role="menuitem",改用 text-based
    await page.getByText("登出", { exact: true }).click();

    // logout 後 redirect 到 /login
    await page.waitForURL(/\/login/, { timeout: 5000 });

    // 嘗試訪問 /dashboard 應再被擋
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("API logout 之後 cookie 已清", async ({ page }) => {
    // 拿 csrf 用來打 logout(storageState 已有 cookie)
    const cookies = await page.context().cookies();
    const csrf = cookies.find((c) => c.name === "csrf_token")?.value;
    expect(csrf).toBeTruthy();

    const r = await page.context().request.post("/api/v1/auth/logout", {
      headers: { "X-CSRF-Token": csrf ?? "" },
      failOnStatusCode: false,
    });
    expect(r.status()).toBe(200);

    const after = await page.context().cookies();
    expect(after.find((c) => c.name === "csrf_token")).toBeUndefined();
    expect(after.find((c) => c.name === "refresh_token")).toBeUndefined();

    // 訪問受保護頁面被擋
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});

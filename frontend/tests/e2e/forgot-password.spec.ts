import { expect, test } from "@playwright/test";

// forgot-password 是 auth route,middleware 會把已登入用戶導離。
// 強制未登入。
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Forgot password flow", () => {
  test("空 email 顯示 zod validation", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.getByRole("button", { name: "發送重置連結" }).click();
    await expect(page.getByText(/請輸入有效的 email/)).toBeVisible();
  });

  test("錯誤 email 格式顯示 zod validation", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("電子郵件").fill("not-an-email");
    await page.getByRole("button", { name: "發送重置連結" }).click();
    await expect(page.getByText(/請輸入有效的 email/)).toBeVisible();
  });

  test("合法 email 送出顯示成功訊息(後端永遠 200 避免帳號探測)", async ({
    page,
  }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("電子郵件").fill("nobody-here@example.com");
    await page.getByRole("button", { name: "發送重置連結" }).click();
    // 訊息同時出現在內聯 <p> 與 sonner toast,用 first() 通過 strict mode
    await expect(
      page.getByText("若該 email 已註冊,系統會寄送重置連結").first(),
    ).toBeVisible({ timeout: 10_000 });
  });
});

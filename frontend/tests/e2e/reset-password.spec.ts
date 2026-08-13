import { expect, test } from "@playwright/test";

// reset-password 是 auth route,強制未登入
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Reset password form validation", () => {
  test("無 token:顯示連結無效訊息 + submit 被 disabled", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(
      page.getByText("連結無效,請從信件中重新點擊"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "確認重置" }),
    ).toBeDisabled();
  });

  test("帶 token,密碼太短 → 顯示「至少 12 字元」 FormMessage", async ({
    page,
  }) => {
    await page.goto("/reset-password?token=fake-token");
    await page.getByLabel("新密碼", { exact: true }).fill("short");
    await page.getByLabel("確認密碼", { exact: true }).fill("short");
    await page.getByRole("button", { name: "確認重置" }).click();
    // CardDescription 也含「至少 12 字元」會 strict mode violation,
    // 改用 FormMessage 的 <p data-slot="form-message">
    await expect(
      page
        .locator('[data-slot="form-message"]')
        .filter({ hasText: "至少 12 字元" }),
    ).toBeVisible();
  });

  test("密碼複雜度不足 → 顯示對應錯誤", async ({ page }) => {
    await page.goto("/reset-password?token=fake-token");
    // 12 字元但都是小寫
    await page
      .getByLabel("新密碼", { exact: true })
      .fill("abcdefghijkl");
    await page
      .getByLabel("確認密碼", { exact: true })
      .fill("abcdefghijkl");
    await page.getByRole("button", { name: "確認重置" }).click();
    // 至少要看到「需含大寫 / 需含數字 / 需含特殊符號」其中一個
    await expect(
      page.getByText(/需含大寫|需含數字|需含特殊符號/),
    ).toBeVisible();
  });

  test("兩次密碼不一致 → 顯示「兩次密碼不一致」", async ({ page }) => {
    await page.goto("/reset-password?token=fake-token");
    await page
      .getByLabel("新密碼", { exact: true })
      .fill("Abcdef!2345Gh");
    await page
      .getByLabel("確認密碼", { exact: true })
      .fill("Abcdef!2345XX");
    await page.getByRole("button", { name: "確認重置" }).click();
    await expect(page.getByText("兩次密碼不一致")).toBeVisible();
  });
});

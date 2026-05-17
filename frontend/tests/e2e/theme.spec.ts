import { expect, test } from "@playwright/test";

test.describe("Theme toggle", () => {
  test("點 Topbar 圖示切換 dark / light", async ({ page }) => {
    await page.goto("/dashboard");

    // 初始狀態(system / light / dark 由 next-themes 決定),
    // 我們只測「點一次後 html class 會變化」+「再點一次切回」。
    const initialClass = await page.evaluate(
      () => document.documentElement.className,
    );

    // 切換按鈕 aria-label = '切換主題'
    const toggle = page.getByRole("button", { name: "切換主題" });
    await toggle.click();

    // 等 html class 變更
    await expect
      .poll(
        async () =>
          await page.evaluate(() => document.documentElement.className),
        { timeout: 3000 },
      )
      .not.toBe(initialClass);

    const afterFirstClass = await page.evaluate(
      () => document.documentElement.className,
    );

    // 再點一次切回
    await toggle.click();
    await expect
      .poll(
        async () =>
          await page.evaluate(() => document.documentElement.className),
        { timeout: 3000 },
      )
      .not.toBe(afterFirstClass);
  });
});

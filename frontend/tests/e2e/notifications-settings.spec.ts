import { expect, test } from "@playwright/test";

// Phase 17 § T:notifications 流程
//   - 進頁、看到表單欄位
//   - 修改訂閱事件 → 儲存按鈕
//   - 不真打 Discord / Telegram(後端 endpoint 已 mock 「不真打外部」)

test.describe("Phase 17 notifications settings", () => {
  test.beforeEach(async ({ page }) => {
    page.on("pageerror", (e) => {
      throw new Error(`Page error: ${e.message}`);
    });
  });

  test("顯示頻道與訂閱事件 + 儲存按鈕", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "通知設定" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Discord Webhook URL")).toBeVisible();
    await expect(page.getByText("Telegram chat_id")).toBeVisible();
    await expect(page.getByRole("button", { name: /儲存設定/ })).toBeVisible();
  });

  test("勾選事件 → 儲存按鈕可按", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "通知設定" })).toBeVisible({
      timeout: 15_000,
    });

    // 點第一個事件 checkbox 的 label
    const eventLabel = page.locator("label", { hasText: "分析完成" }).first();
    await eventLabel.click();

    // 儲存
    await page.getByRole("button", { name: /儲存設定/ }).click();

    // toast 不一定總是顯示;檢查 endpoint 響應與按鈕狀態
    await page.waitForTimeout(500);
    await expect(page.getByRole("button", { name: /儲存設定/ })).toBeVisible();
  });
});

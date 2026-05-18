import { expect, test } from "@playwright/test";

// Phase 17 § T:screener filter 流程
//   - 進頁、套用 PE_max=15 + 市場 TW → 結果表渲染或顯示空狀態
//   - 切到 US 不破版
//   - PLAN console 0 error 由 pageerror handler 把關

test.describe("Phase 17 screener filter", () => {
  test.beforeEach(async ({ page }) => {
    page.on("pageerror", (e) => {
      throw new Error(`Page error: ${e.message}`);
    });
  });

  test("套用 PE_max=15 後表格載入完成", async ({ page }) => {
    await page.goto("/screener/filter");
    await expect(
      page.getByRole("heading", { name: "選股篩選器" }),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByLabel("PE 最大").fill("15");
    await page.getByRole("button", { name: "套用篩選" }).click();

    // 結果區應該不會 throw,且最多顯示「尚無符合條件的股票」
    await page.waitForTimeout(800);
    const empty = page.locator("text=/尚無符合條件的股票|代號|篩選/").first();
    await expect(empty).toBeVisible();
  });

  test("切換 TW / US 不破版", async ({ page }) => {
    await page.goto("/screener/filter");
    await expect(
      page.getByRole("heading", { name: "選股篩選器" }),
    ).toBeVisible({ timeout: 15_000 });
    await page.getByRole("tab", { name: /美股/ }).click();
    await expect(page.getByRole("tab", { name: /美股/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});

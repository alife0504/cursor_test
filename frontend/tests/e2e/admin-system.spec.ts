import { expect, test } from "@playwright/test";

// Phase 17 § T:admin system 流程
//   - admin 登入後可進 /admin/system
//   - 顯示 mock banner + 6 個指標卡片

test.describe("Phase 17 admin system metrics", () => {
  test.beforeEach(async ({ page }) => {
    page.on("pageerror", (e) => {
      throw new Error(`Page error: ${e.message}`);
    });
  });

  test("/admin/system 顯示 Mock banner 與卡片", async ({ page }) => {
    await page.goto("/admin/system");
    await expect(page.getByRole("heading", { name: "系統監控" })).toBeVisible({
      timeout: 15_000,
    });
    // mock banner 必含
    await expect(page.getByTestId("mock-banner")).toBeVisible();
    // 至少幾張指標卡片
    await expect(page.getByText("API 可用性")).toBeVisible();
    await expect(page.getByText("今日 LLM 成本")).toBeVisible();
    await expect(page.getByText("佇列長度")).toBeVisible();
  });

  test("/admin/pipeline 顯示 DLQ 區塊", async ({ page }) => {
    await page.goto("/admin/pipeline");
    await expect(page.getByRole("heading", { name: "資料管線管理" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Dead Letter Queue/)).toBeVisible();
  });
});

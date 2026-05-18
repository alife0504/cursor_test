// Phase 15 E2E 共用 helper
//
// 在 globalSetup(tests/e2e/global.setup.ts)一次 login 後,所有需登入的 spec
// 都會自動載入 storageState(playwright.config.ts 配置)。不需要再用 fixture
// 把 cookie 寫進每個 test 的 context。
//
// 未登入測試請用:test.use({ storageState: { cookies: [], origins: [] } });
//
// 此檔保留為向後相容:某些 spec 仍 import 自此(loggedInPage 直接等於 page,
// apiLogin 變 no-op,因為 storageState 已含 cookie)。
import { test as base, expect } from "@playwright/test";

interface Fixtures {
  apiLogin: () => Promise<void>;
  loggedInPage: import("@playwright/test").Page;
}

export const test = base.extend<Fixtures>({
  apiLogin: async ({}, use) => {
    // no-op:globalSetup 已 login,storageState 已寫好
    await use(async () => undefined);
  },
  loggedInPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect };

import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// Phase 15 § X:Playwright E2E
//   - 預設 baseURL = dev server localhost:3000(本機跑 npm run dev + backend docker compose up)
//   - 兩個 project:
//       1. setup:跑一次 login,存 storageState 到 tests/e2e/.auth/admin.json
//          (避開 backend L2 rate limit 5/min/IP)
//       2. chromium:所有 spec 用該 storageState,depends on setup
//   - auth-related spec(login error / forgot / reset)用 `test.use({ storageState: { cookies: [], origins: [] } })`
//     強制覆寫成空 cookie state,模擬未登入。

const AUTH_FILE = path.join(__dirname, "tests/e2e/.auth/admin.json");

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "setup",
      testMatch: /global\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: AUTH_FILE,
      },
      dependencies: ["setup"],
    },
  ],
});

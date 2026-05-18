import { test } from "@playwright/test";

// 對應 PLAN § 21 完整 18 頁(扣掉 dashboard 已經是登入後預設),
// 加上 P15 任務 Q 補的 analysis/[id] 我們不在 nav 顯示。
const NAV_LEAVES: Array<{ label: string; path: string; group?: string }> = [
  { label: "儀表板", path: "/dashboard" },
  { group: "市場", label: "市場總覽", path: "/market/overview" },
  { group: "市場", label: "三大法人", path: "/market/institutional" },
  { group: "市場", label: "財報日曆", path: "/market/calendar" },
  { group: "選股", label: "自選股清單", path: "/screener/watchlist" },
  { group: "選股", label: "選股篩選器", path: "/screener/filter" },
  { group: "選股", label: "多股比較", path: "/screener/compare" },
  { group: "AI 分析", label: "新增分析", path: "/analysis/new" },
  { group: "AI 分析", label: "分析歷史", path: "/analysis/history" },
  { group: "績效統計", label: "準確率分析", path: "/statistics/accuracy" },
  { group: "績效統計", label: "模型比較", path: "/statistics/models" },
  { group: "績效統計", label: "回測結果", path: "/statistics/backtest" },
  { group: "投資組合", label: "模擬持倉", path: "/portfolio/positions" },
  { group: "投資組合", label: "待核准訂單", path: "/portfolio/orders" },
  { group: "投資組合", label: "交易記錄", path: "/portfolio/history" },
  { group: "資訊", label: "新聞情緒", path: "/news/sentiment" },
  { group: "資訊", label: "重大公告", path: "/news/announcements" },
  { label: "通知設定", path: "/notifications" },
  { group: "管理", label: "用戶管理", path: "/admin/users" },
  { group: "管理", label: "審計日誌", path: "/admin/audit" },
  { group: "管理", label: "系統監控", path: "/admin/system" },
  { group: "管理", label: "資料管線", path: "/admin/pipeline" },
];

test.describe("Sidebar 18 nav", () => {
  for (const item of NAV_LEAVES) {
    test(`點 「${item.label}」 → ${item.path}`, async ({ page }) => {
      await page.goto("/dashboard");

      // 若有 group(Collapsible)先展開
      if (item.group) {
        const groupBtn = page.getByRole("button", { name: item.group });
        // 若 group 在預設 close 狀態才展開
        try {
          await groupBtn.click({ timeout: 1000 });
        } catch {
          // group 可能已展開或為 leaf,忽略
        }
      }

      const link = page.getByRole("link", { name: item.label });
      await link.first().click();
      await page.waitForURL(new RegExp(item.path.replace(/\//g, "\\/")), {
        timeout: 5000,
      });
    });
  }
});

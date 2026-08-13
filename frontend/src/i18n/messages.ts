// Phase 15 + v1.0.1：i18n 字典（zh-TW 為主、en fallback 到 zh-TW）。
// v2 之後接 next-intl；目前用最簡 key-value lookup。

export type Locale = "zh-TW" | "en";

type Messages = Record<string, string>;

const ZH_TW: Messages = {
  // 應用基本
  "app.title": "TradingAgents-TW",
  "app.tagline": "台股 / 美股 AI 多智能體交易分析",
  "app.brand.subtitle": "Secure Edition",
  "app.version": "v1.0.1",

  // 認證
  "auth.login.title": "登入",
  "auth.login.email": "電子郵件",
  "auth.login.password": "密碼",
  "auth.login.submit": "登入",
  "auth.login.forgot": "忘記密碼？",
  "auth.login.error.invalid": "電子郵件或密碼錯誤",
  "auth.login.error.locked": "帳號已鎖定，請稍後再試",
  "auth.login.error.generic": "登入失敗，請稍後再試",
  "auth.forgot.title": "忘記密碼",
  "auth.forgot.submit": "發送重置連結",
  "auth.forgot.success": "若該 email 已註冊，系統會寄送重置連結",
  "auth.reset.title": "重置密碼",
  "auth.reset.new_password": "新密碼",
  "auth.reset.confirm_password": "確認密碼",
  "auth.reset.submit": "確認重置",
  "auth.reset.success": "密碼已重置，請以新密碼登入",

  // Onboarding
  "onboarding.change_pw.title": "首次登入，請設定新密碼",
  "onboarding.change_pw.old": "目前密碼",
  "onboarding.change_pw.new": "新密碼",
  "onboarding.change_pw.confirm": "確認新密碼",
  "onboarding.change_pw.rules":
    "至少 12 字元，包含大寫、小寫、數字、特殊符號 4 類",
  "onboarding.change_pw.submit": "更新密碼",
  "onboarding.welcome.title": "歡迎使用 TradingAgents-TW",
  "onboarding.welcome.desc":
    "本系統提供台股 / 美股 AI 多智能體分析。先帶你瀏覽幾個重點功能。",
  "onboarding.welcome.cta": "前往儀表板",

  // Navigation
  "nav.dashboard": "儀表板",
  "nav.market": "市場",
  "nav.market.overview": "市場總覽",
  "nav.market.institutional": "三大法人",
  "nav.market.calendar": "財報日曆",
  "nav.screener": "選股",
  "nav.screener.watchlist": "自選股清單",
  "nav.screener.filter": "選股篩選器",
  "nav.screener.compare": "多股比較",
  "nav.analysis": "AI 分析",
  "nav.analysis.new": "新增分析",
  "nav.analysis.history": "分析歷史",
  "nav.statistics": "績效統計",
  "nav.statistics.accuracy": "準確率分析",
  "nav.statistics.models": "模型比較",
  "nav.statistics.backtest": "回測結果",
  "nav.portfolio": "投資組合",
  "nav.portfolio.positions": "模擬持倉",
  "nav.portfolio.orders": "待核准訂單",
  "nav.portfolio.history": "交易記錄",
  "nav.news": "資訊",
  "nav.news.sentiment": "新聞情緒",
  "nav.news.announcements": "重大公告",
  "nav.notifications": "通知設定",
  "nav.admin": "管理",
  "nav.admin.users": "用戶管理",
  "nav.admin.audit": "審計日誌",
  "nav.admin.system": "系統監控",
  "nav.admin.pipeline": "資料管線",

  // Topbar
  "topbar.theme.toggle": "切換主題",
  "topbar.logout": "登出",
  "topbar.account": "帳號",
  "topbar.search.hint": "搜尋股票、頁面、分析...",
  "topbar.notifications.unread": "有新通知",
  "topbar.menu.open": "開啟選單",

  // 共用
  "common.loading": "載入中...",
  "common.empty": "目前沒有資料",
  "common.error": "發生錯誤",
  "common.retry": "重試",
  "common.cancel": "取消",
  "common.confirm": "確認",
  "common.save": "儲存",
  "common.delete": "刪除",
  "common.edit": "編輯",
  "common.search": "搜尋",
  "common.next": "下一頁",
  "common.previous": "上一頁",
  "common.refresh": "重新整理",
  "common.export": "匯出",
  "common.share": "分享連結",
  "common.copy.success": "已複製",
  "common.copy.fail": "複製失敗",

  // 錯誤態
  "error.load_failed": "載入失敗",
  "error.network": "網路連線失敗",
  "error.unauthorized": "未授權",
  "error.forbidden": "權限不足",
  "error.not_found": "找不到資源",
  "error.server": "伺服器內部錯誤",

  // 空態
  "empty.default.title": "目前沒有資料",
  "empty.no_results": "找不到符合的結果",

  // Stub / Mock
  "page.stub.title": "頁面建設中",
  "page.stub.desc": "此頁面將在後續版本實作完成",
  "page.mock.banner": "Mock 資料 — v1.1 將完整實作",

  // Market
  "market.tw": "台股",
  "market.us": "美股",
  "market.taiex": "加權指數",
  "market.tpex": "櫃買指數",
  "market.advancers": "上漲",
  "market.decliners": "下跌",
  "market.unchanged": "平盤",
  "market.volume": "成交量",

  // Signal
  "signal.buy": "買進",
  "signal.sell": "賣出",
  "signal.hold": "持有",

  // Status
  "status.queued": "排隊中",
  "status.running": "分析中",
  "status.completed": "已完成",
  "status.failed": "失敗",
  "status.cancelled": "已取消",
  "status.pending": "待核准",
  "status.approved": "已核准",
  "status.rejected": "已拒絕",
  "status.expired": "已過期",

  // Dashboard
  "dashboard.title": "儀表板",
  "dashboard.kpi.quota": "本月 LLM 配額",
  "dashboard.kpi.pending_orders": "待核准訂單",
  "dashboard.alerts.title": "今日重點",
  "dashboard.alerts.empty": "今日尚無新事件",
  "dashboard.quick.new_analysis": "新增分析",
  "dashboard.quick.watchlist": "加入自選股",
  "dashboard.quick.orders": "看待核准訂單",
  "dashboard.quick.notifications": "通知設定",

  // Analysis
  "analysis.new.title": "新增分析",
  "analysis.new.desc": "選股 → 選 analyst → 選模型 → 選辯論輪數 → 送出",
  "analysis.detail.tab.overview": "Overview",
  "analysis.detail.tab.analysts": "Analysts",
  "analysis.detail.tab.debate": "Debate",
  "analysis.detail.tab.report": "Report",
  "analysis.stepper.queue": "排隊中",
  "analysis.stepper.analysts": "Analyst 分析",
  "analysis.stepper.debate": "多空辯論",
  "analysis.stepper.manager": "Manager 綜合",
  "analysis.stepper.done": "完成",

  // Portfolio
  "portfolio.positions.title": "模擬持倉",
  "portfolio.orders.title": "待核准訂單",
  "portfolio.history.title": "交易記錄",
  "portfolio.approval.title": "核准訂單（雙重確認）",
  "portfolio.reject.title": "拒絕訂單",
  "portfolio.confirm.label": "我已核對代號、方向、數量與止損/止盈，同意送出核准",

  // Side
  "side.buy": "買進",
  "side.sell": "賣出",
};

const EN: Messages = {
  "app.title": "TradingAgents-TW",
  "app.tagline": "TW / US AI Multi-Agent Trading Analysis",
  "app.brand.subtitle": "Secure Edition",
};

const dict: Record<Locale, Messages> = {
  "zh-TW": ZH_TW,
  en: EN,
};

let currentLocale: Locale = "zh-TW";

export function setLocale(locale: Locale) {
  currentLocale = locale;
}

export function getLocale(): Locale {
  return currentLocale;
}

export function t(key: string, locale?: Locale): string {
  const lang = locale ?? currentLocale;
  return dict[lang]?.[key] ?? dict["zh-TW"][key] ?? key;
}

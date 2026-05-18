// Phase 15 § U:i18n 雛形(只先做 zh-TW + 預留 en)
// v2 之後接 next-intl,目前用最簡 key-value lookup

export type Locale = "zh-TW" | "en";

type Messages = Record<string, string>;

const dict: Record<Locale, Messages> = {
  "zh-TW": {
    "app.title": "TradingAgents-TW",
    "app.tagline": "台股 / 美股 AI 多智能體交易分析",

    "auth.login.title": "登入",
    "auth.login.email": "電子郵件",
    "auth.login.password": "密碼",
    "auth.login.submit": "登入",
    "auth.login.forgot": "忘記密碼?",
    "auth.login.error.invalid": "電子郵件或密碼錯誤",
    "auth.login.error.locked": "帳號已鎖定,請稍後再試",
    "auth.login.error.generic": "登入失敗,請稍後再試",
    "auth.forgot.title": "忘記密碼",
    "auth.forgot.submit": "發送重置連結",
    "auth.forgot.success": "若該 email 已註冊,系統會寄送重置連結",
    "auth.reset.title": "重置密碼",
    "auth.reset.new_password": "新密碼",
    "auth.reset.confirm_password": "確認密碼",
    "auth.reset.submit": "確認重置",
    "auth.reset.success": "密碼已重置,請以新密碼登入",

    "onboarding.change_pw.title": "首次登入,請設定新密碼",
    "onboarding.change_pw.old": "目前密碼",
    "onboarding.change_pw.new": "新密碼",
    "onboarding.change_pw.confirm": "確認新密碼",
    "onboarding.change_pw.rules":
      "至少 12 字元,包含大寫、小寫、數字、特殊符號 4 類",
    "onboarding.change_pw.submit": "更新密碼",
    "onboarding.welcome.title": "歡迎使用 TradingAgents-TW",
    "onboarding.welcome.desc":
      "本系統提供台股 / 美股 AI 多智能體分析。先帶你瀏覽幾個重點功能。",
    "onboarding.welcome.cta": "前往儀表板",

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

    "topbar.theme.toggle": "切換主題",
    "topbar.logout": "登出",
    "topbar.account": "帳號",

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

    "page.stub.title": "頁面建設中",
    "page.stub.desc": "此頁面將在後續 Phase(P16/P17)實作完成",

    "market.tw": "台股",
    "market.us": "美股",
  },
  en: {
    "app.title": "TradingAgents-TW",
    "app.tagline": "TW / US AI Multi-Agent Trading Analysis",
  },
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

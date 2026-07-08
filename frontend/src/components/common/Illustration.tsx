import { cn } from "@/lib/utils";

/**
 * 品牌 SVG spot 插畫庫 — 純裝飾（aria-hidden），零依賴。
 *
 * 設計規範：
 * - 顏色一律走設計系統 CSS 變數（hsl(var(--...))）→ 深淺色模式自動適應
 * - 幾何扁平風：大圓底 + 虛線軌道 + 主題元素 + 星點點綴
 * - 金融語彙：K 線用台股慣例「紅漲綠跌」（--bull / --bear）
 * - `agents` 為深色底（登入 hero / 品牌漸層橫幅）專用的白色線稿版
 */
export type IllustrationName =
  | "empty"
  | "search"
  | "error"
  | "chart"
  | "agents";

interface IllustrationProps {
  name: IllustrationName;
  className?: string;
}

/** 共用點綴：加號星芒 + 圓點（散佈在大圓外圍） */
function Sparkles() {
  return (
    <g strokeLinecap="round">
      <path
        d="M34 34v10M29 39h10"
        stroke="hsl(var(--chart-2) / 0.7)"
        strokeWidth="2"
      />
      <path
        d="M164 88v8M160 92h8"
        stroke="hsl(var(--primary) / 0.45)"
        strokeWidth="2"
      />
      <circle cx="166" cy="42" r="3" fill="hsl(var(--chart-3) / 0.6)" />
      <circle cx="42" cy="98" r="2.5" fill="hsl(var(--info) / 0.55)" />
      <circle cx="148" cy="24" r="2" fill="hsl(var(--chart-2) / 0.5)" />
    </g>
  );
}

/** 共用背景：大圓底 + 虛線軌道 */
function Backdrop({ tint = "--primary" }: { tint?: string }) {
  return (
    <>
      <circle cx="100" cy="64" r="50" fill={`hsl(var(${tint}) / 0.07)`} />
      <circle
        cx="100"
        cy="64"
        r="61"
        fill="none"
        stroke="hsl(var(--border))"
        strokeWidth="1.5"
        strokeDasharray="2 7"
        strokeLinecap="round"
      />
    </>
  );
}

/** 空狀態：收件匣 + 漂浮的 K 線報告單 */
function EmptyScene() {
  return (
    <svg
      viewBox="0 0 200 140"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="h-full w-auto"
    >
      <Backdrop />
      <Sparkles />
      {/* 地面陰影 */}
      <ellipse cx="100" cy="118" rx="42" ry="5" fill="hsl(var(--foreground) / 0.05)" />
      {/* 收件匣 */}
      <rect
        x="62"
        y="76"
        width="76"
        height="36"
        rx="9"
        fill="hsl(var(--card))"
        stroke="hsl(var(--primary) / 0.4)"
        strokeWidth="1.5"
      />
      <path
        d="M62 90h20l7 9h22l7-9h20"
        stroke="hsl(var(--primary) / 0.4)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        fill="hsl(var(--primary) / 0.06)"
      />
      {/* 漂浮報告單（外層 g 跑 CSS 浮動動畫，內層 g 負責旋轉，避免 transform 打架） */}
      <g className="animate-float-y">
        <g transform="rotate(7 118 44)">
          <rect
            x="104"
            y="26"
            width="28"
            height="34"
            rx="5"
            fill="hsl(var(--muted))"
            opacity="0.9"
          />
        </g>
        <g transform="rotate(-7 86 46)">
          <rect
            x="70"
            y="28"
            width="32"
            height="40"
            rx="5"
            fill="hsl(var(--card))"
            stroke="hsl(var(--border))"
            strokeWidth="1.5"
          />
          {/* 標題列 */}
          <rect x="76" y="34" width="14" height="3" rx="1.5" fill="hsl(var(--muted-foreground) / 0.35)" />
          {/* 迷你 K 線（紅漲綠跌） */}
          <path d="M81 60v-16" stroke="hsl(var(--bull))" strokeWidth="1.2" />
          <rect x="79" y="48" width="4" height="8" rx="1" fill="hsl(var(--bull))" />
          <path d="M89 62v-14" stroke="hsl(var(--bear))" strokeWidth="1.2" />
          <rect x="87" y="51" width="4" height="7" rx="1" fill="hsl(var(--bear))" />
          <path d="M97 58v-16" stroke="hsl(var(--bull))" strokeWidth="1.2" />
          <rect x="95" y="45" width="4" height="9" rx="1" fill="hsl(var(--bull))" />
        </g>
      </g>
    </svg>
  );
}

/** 搜尋：放大鏡裡的趨勢線 */
function SearchScene() {
  return (
    <svg
      viewBox="0 0 200 140"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="h-full w-auto"
    >
      <Backdrop tint="--info" />
      <Sparkles />
      <ellipse cx="100" cy="118" rx="38" ry="5" fill="hsl(var(--foreground) / 0.05)" />
      {/* 鏡柄 */}
      <path
        d="M112 78l17 17"
        stroke="hsl(var(--primary) / 0.6)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      {/* 鏡框 + 鏡片 */}
      <circle
        cx="94"
        cy="60"
        r="25"
        fill="hsl(var(--card) / 0.85)"
        stroke="hsl(var(--primary) / 0.55)"
        strokeWidth="3"
      />
      {/* 鏡片內趨勢線 */}
      <path
        d="M81 68l7-9 6 5 8-12 6 4"
        stroke="hsl(var(--chart-1))"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="108" cy="56" r="2.5" fill="hsl(var(--chart-1))" />
      {/* 鏡片高光 */}
      <path
        d="M80 51a17 17 0 016-6"
        stroke="hsl(var(--primary) / 0.25)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** 錯誤：走勢中斷的圖表卡 + 警示徽章 */
function ErrorScene() {
  return (
    <svg
      viewBox="0 0 200 140"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="h-full w-auto"
    >
      <Backdrop tint="--destructive" />
      <ellipse cx="100" cy="118" rx="42" ry="5" fill="hsl(var(--foreground) / 0.05)" />
      {/* 點綴（收斂版，避免搶了警示焦點） */}
      <g strokeLinecap="round">
        <path d="M36 42v8M32 46h8" stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth="2" />
        <circle cx="162" cy="38" r="2.5" fill="hsl(var(--muted-foreground) / 0.35)" />
      </g>
      {/* 圖表卡 */}
      <rect
        x="58"
        y="38"
        width="84"
        height="58"
        rx="9"
        fill="hsl(var(--card))"
        stroke="hsl(var(--border))"
        strokeWidth="1.5"
      />
      {/* 正常段走勢 */}
      <path
        d="M66 84l14-13 10 6 10-15"
        stroke="hsl(var(--chart-1))"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 斷裂缺口 */}
      <path d="M102 56l4 8M107 54l4 8" stroke="hsl(var(--destructive) / 0.5)" strokeWidth="1.5" strokeLinecap="round" />
      {/* 斷線下墜段 */}
      <path
        d="M114 62l14 20"
        stroke="hsl(var(--destructive))"
        strokeWidth="2"
        strokeDasharray="4 3"
        strokeLinecap="round"
      />
      {/* 警示徽章 */}
      <circle cx="136" cy="90" r="13" fill="hsl(var(--destructive))" stroke="hsl(var(--card))" strokeWidth="3" />
      <path d="M136 84v7" stroke="hsl(var(--destructive-foreground))" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="136" cy="96" r="1.6" fill="hsl(var(--destructive-foreground))" />
    </svg>
  );
}

/** 成長圖表：上升柱 + 紅色（台股漲）趨勢箭頭 */
function ChartScene() {
  return (
    <svg
      viewBox="0 0 200 140"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="h-full w-auto"
    >
      <Backdrop />
      <Sparkles />
      <ellipse cx="100" cy="118" rx="42" ry="5" fill="hsl(var(--foreground) / 0.05)" />
      {/* 上升柱 */}
      <rect x="68" y="78" width="15" height="26" rx="3" fill="hsl(var(--chart-1) / 0.35)" />
      <rect x="89" y="66" width="15" height="38" rx="3" fill="hsl(var(--chart-1) / 0.6)" />
      <rect x="110" y="52" width="15" height="52" rx="3" fill="hsl(var(--primary))" />
      {/* 趨勢箭頭（紅＝漲） */}
      <path
        d="M62 74l24-14 12 5 26-22"
        stroke="hsl(var(--bull))"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M115 42l9 1 1 9"
        stroke="hsl(var(--bull))"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* 金幣 */}
      <g className="animate-float-y">
        <circle cx="142" cy="82" r="10" fill="hsl(var(--chart-2))" stroke="hsl(var(--card))" strokeWidth="2" />
        <circle cx="142" cy="82" r="6" fill="none" stroke="hsl(0 0% 100% / 0.55)" strokeWidth="1.5" />
      </g>
    </svg>
  );
}

/**
 * 多 Agent 協作網絡（深色底專用白色線稿）：
 * 4 位分析師 → 辯論中樞（Manager）→ 輸出訊號
 */
function AgentsScene() {
  return (
    <svg
      viewBox="0 0 260 160"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="h-full w-auto"
    >
      {/* 連線（分析師 → 中樞） */}
      <path d="M48 34C80 40 96 60 112 72" stroke="hsl(0 0% 100% / 0.25)" strokeWidth="1.5" />
      <path d="M48 68C74 72 92 76 110 79" stroke="hsl(0 0% 100% / 0.25)" strokeWidth="1.5" strokeDasharray="1 5" strokeLinecap="round" />
      <path d="M48 100C74 96 92 90 110 85" stroke="hsl(0 0% 100% / 0.25)" strokeWidth="1.5" />
      <path d="M48 132C80 126 96 102 112 90" stroke="hsl(0 0% 100% / 0.25)" strokeWidth="1.5" strokeDasharray="1 5" strokeLinecap="round" />
      {/* 分析師節點 × 4（技術 / 基本 / 新聞 / 籌碼） */}
      <g>
        <circle cx="36" cy="32" r="12" fill="hsl(0 0% 100% / 0.1)" stroke="hsl(0 0% 100% / 0.4)" strokeWidth="1.5" />
        <path d="M32 36v-5M36 36v-8M40 36v-3" stroke="hsl(0 0% 100% / 0.8)" strokeWidth="1.5" strokeLinecap="round" />
      </g>
      <g>
        <circle cx="36" cy="66" r="12" fill="hsl(0 0% 100% / 0.1)" stroke="hsl(0 0% 100% / 0.4)" strokeWidth="1.5" />
        <path d="M31 62h10M31 66h10M31 70h6" stroke="hsl(0 0% 100% / 0.8)" strokeWidth="1.5" strokeLinecap="round" />
      </g>
      <g>
        <circle cx="36" cy="100" r="12" fill="hsl(0 0% 100% / 0.1)" stroke="hsl(0 0% 100% / 0.4)" strokeWidth="1.5" />
        <path d="M30 100a6 6 0 1112 0M30 100h12" stroke="hsl(0 0% 100% / 0.8)" strokeWidth="1.5" strokeLinecap="round" />
      </g>
      <g>
        <circle cx="36" cy="134" r="12" fill="hsl(0 0% 100% / 0.1)" stroke="hsl(0 0% 100% / 0.4)" strokeWidth="1.5" />
        <circle cx="36" cy="134" r="5.5" stroke="hsl(0 0% 100% / 0.8)" strokeWidth="1.5" />
        <path d="M36 128.5v5.5l4 3.5" stroke="hsl(0 0% 100% / 0.8)" strokeWidth="1.5" strokeLinecap="round" />
      </g>
      {/* 中樞（Manager） */}
      <circle cx="132" cy="82" r="21" fill="hsl(0 0% 100% / 0.12)" stroke="hsl(0 0% 100% / 0.55)" strokeWidth="1.5" />
      <circle cx="132" cy="82" r="29" fill="none" stroke="hsl(0 0% 100% / 0.18)" strokeWidth="1" strokeDasharray="2 6" strokeLinecap="round" />
      {/* 星芒（AI） */}
      <path
        d="M132 71l2.6 7.4 7.4 2.6-7.4 2.6-2.6 7.4-2.6-7.4-7.4-2.6 7.4-2.6z"
        fill="hsl(0 0% 100% / 0.9)"
      />
      {/* 輸出 → 訊號卡 */}
      <path d="M156 82h48" stroke="hsl(0 0% 100% / 0.4)" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M200 77l6 5-6 5" stroke="hsl(0 0% 100% / 0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="212" y="64" width="38" height="36" rx="9" fill="hsl(0 0% 100% / 0.12)" stroke="hsl(0 0% 100% / 0.45)" strokeWidth="1.5" />
      <path
        d="M220 90l7-8 5 4 9-11"
        stroke="hsl(0 0% 100% / 0.85)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 星點 */}
      <circle cx="96" cy="30" r="2" fill="hsl(0 0% 100% / 0.35)" />
      <circle cx="182" cy="42" r="2.5" fill="hsl(0 0% 100% / 0.3)" />
      <circle cx="170" cy="126" r="2" fill="hsl(0 0% 100% / 0.3)" />
      <path d="M226 34v8M222 38h8" stroke="hsl(0 0% 100% / 0.35)" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M88 132v8M84 136h8" stroke="hsl(0 0% 100% / 0.3)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

const SCENES: Record<IllustrationName, () => JSX.Element> = {
  empty: EmptyScene,
  search: SearchScene,
  error: ErrorScene,
  chart: ChartScene,
  agents: AgentsScene,
};

export function Illustration({ name, className }: IllustrationProps) {
  const Scene = SCENES[name];
  return (
    <div aria-hidden="true" className={cn("select-none", className)}>
      <Scene />
    </div>
  );
}

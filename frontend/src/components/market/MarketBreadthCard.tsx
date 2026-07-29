"use client";

/** 漲跌家數圓餅 ＋ 市場摘要（合併精簡卡）：甜甜圈在上、家數在右、漲停/跌停與摘要在下。 */
export function MarketBreadthCard({
  adv,
  dec,
  unc,
  limitUp,
  limitDown,
  totalVolume,
  live,
}: {
  adv: number;
  dec: number;
  unc: number;
  limitUp: number;
  limitDown: number;
  totalVolume: number | null;
  live: boolean;
}) {
  const total = adv + dec + unc;
  const C = 2 * Math.PI * 52; // 周長
  const seg = (n: number) => (total > 0 ? (n / total) * C : 0);
  const advLen = seg(adv);
  const decLen = seg(dec);
  const uncLen = seg(unc);

  // 色卡顏色要用 hsl(var(--x))——globals.css 的 --bull/--bear/--flat 是 HSL 三元組（如 0 75% 50%），
  // 直接 var(--bull) 當 background 是無效值 → 色卡不顯色。與甜甜圈同一種寫法才會有顏色。
  const rows: [string, number, string][] = [
    ["上漲", adv, "hsl(var(--bull))"],
    ["下跌", dec, "hsl(var(--bear))"],
    ["平盤", unc, "hsl(var(--flat))"],
  ];

  return (
    <section className="flex flex-col gap-4 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">漲跌家數分佈</h3>
        <span className="text-[11px] text-muted-foreground">
          市場摘要 {live ? <span className="text-bull/80">· 即時</span> : "· 收盤"}
        </span>
      </div>

      <div className="flex flex-col items-center gap-3">
        <div className="relative h-[152px] w-[152px] shrink-0">
          <svg viewBox="0 0 120 120" className="h-[152px] w-[152px]">
            <circle cx="60" cy="60" r="52" fill="none" stroke="hsl(var(--muted))" strokeWidth="14" />
            <g transform="rotate(-90 60 60)" fill="none" strokeWidth="14">
              <circle cx="60" cy="60" r="52" stroke="hsl(var(--bull))" strokeDasharray={`${advLen} ${C}`} />
              <circle cx="60" cy="60" r="52" stroke="hsl(var(--bear))" strokeDasharray={`${decLen} ${C}`} strokeDashoffset={-advLen} />
              <circle cx="60" cy="60" r="52" stroke="hsl(var(--flat))" strokeDasharray={`${uncLen} ${C}`} strokeDashoffset={-(advLen + decLen)} />
            </g>
          </svg>
          <div className="absolute inset-0 grid place-content-center text-center">
            <span className="num text-xl font-bold tabular-nums">{total.toLocaleString()}</span>
            <span className="text-[11px] text-muted-foreground">總檔數</span>
          </div>
        </div>

        <dl className="flex w-full flex-col gap-2">
          {rows.map(([label, n, color]) => (
            <div key={label} className="flex items-center gap-2">
              {/* 色卡（辨識用）＋較小的標籤字 */}
              <span
                className="h-3 w-3 shrink-0 rounded-[3px] ring-1 ring-black/5"
                style={{ background: color }}
              />
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="num ml-auto text-sm font-semibold tabular-nums">
                {n.toLocaleString()}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {/* 漲停 / 跌停 ＋ 摘要：2×2；漲停紅、跌停綠，醒目呈現「幾家」 */}
      <div className="grid grid-cols-2 gap-2 border-t border-dashed pt-3">
        <div className="rounded-md bg-muted/40 px-2.5 py-2">
          <div className="text-[11px] text-muted-foreground">漲停</div>
          <div className="num text-lg font-bold leading-tight tabular-nums text-bull">
            {limitUp.toLocaleString()}
            <span className="ml-0.5 text-xs font-normal text-muted-foreground">家</span>
          </div>
        </div>
        <div className="rounded-md bg-muted/40 px-2.5 py-2">
          <div className="text-[11px] text-muted-foreground">跌停</div>
          <div className="num text-lg font-bold leading-tight tabular-nums text-bear">
            {limitDown.toLocaleString()}
            <span className="ml-0.5 text-xs font-normal text-muted-foreground">家</span>
          </div>
        </div>
        <div className="px-2.5">
          <div className="text-[11px] text-muted-foreground">總成交量</div>
          <div className="num text-sm font-bold tabular-nums">
            {totalVolume != null ? `${(totalVolume / 1e8).toFixed(1)} 億股` : "—"}
          </div>
        </div>
        <div className="px-2.5">
          <div className="text-[11px] text-muted-foreground">漲 / 跌 家數比</div>
          <div className="num text-sm font-bold tabular-nums">
            {dec > 0 ? (adv / dec).toFixed(2) : "—"}
          </div>
        </div>
      </div>
    </section>
  );
}

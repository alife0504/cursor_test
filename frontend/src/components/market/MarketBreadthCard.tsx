"use client";

/** 漲跌家數圓餅 ＋ 市場摘要（合併精簡卡）：甜甜圈在上、家數在右、摘要在下。 */
export function MarketBreadthCard({
  adv,
  dec,
  unc,
  totalVolume,
  live,
}: {
  adv: number;
  dec: number;
  unc: number;
  totalVolume: number | null;
  live: boolean;
}) {
  const total = adv + dec + unc;
  const C = 2 * Math.PI * 52; // 周長
  const seg = (n: number) => (total > 0 ? (n / total) * C : 0);
  const advLen = seg(adv);
  const decLen = seg(dec);
  const uncLen = seg(unc);
  const advPct = total > 0 ? Math.round((adv / total) * 100) : 0;

  const rows: [string, number, string][] = [
    ["上漲", adv, "var(--bull, #e0384b)"],
    ["下跌", dec, "var(--bear, #0f9d63)"],
    ["平盤", unc, "var(--flat, #94a1b2)"],
  ];

  return (
    <section className="flex flex-col gap-4 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">漲跌家數分佈</h3>
        <span className="text-[11px] text-muted-foreground">
          市場摘要 {live ? <span className="text-bull/80">· 即時</span> : "· 收盤"}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative h-[128px] w-[128px] shrink-0">
          <svg viewBox="0 0 120 120" className="h-[128px] w-[128px]">
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

        <dl className="flex flex-1 flex-col gap-2.5">
          {rows.map(([label, n, color]) => (
            <div key={label} className="flex items-center gap-2 text-sm">
              <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: color }} />
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="num ml-auto font-semibold tabular-nums">{n.toLocaleString()}</dd>
            </div>
          ))}
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            上漲占 <span className="num font-medium text-bull">{advPct}%</span>
          </div>
        </dl>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-dashed pt-3">
        <div>
          <div className="text-[11px] text-muted-foreground">總成交量</div>
          <div className="num text-sm font-bold tabular-nums">
            {totalVolume != null ? `${(totalVolume / 1e8).toFixed(1)} 億股` : "—"}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-muted-foreground">漲 / 跌 家數比</div>
          <div className="num text-sm font-bold tabular-nums">
            {dec > 0 ? (adv / dec).toFixed(2) : "—"}
          </div>
        </div>
      </div>
    </section>
  );
}

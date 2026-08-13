import BigNumber from "bignumber.js";
import dayjs from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

dayjs.extend(utc);
dayjs.extend(timezone);

// BigNumber 全域:不要科學記號,夠用的精度
BigNumber.config({
  EXPONENTIAL_AT: 1e9,
  DECIMAL_PLACES: 20,
});

export type Numeric = string | number | BigNumber;

const safeBn = (value: Numeric): BigNumber | null => {
  if (value === null || value === undefined || value === "") return null;
  const bn = new BigNumber(value);
  if (bn.isNaN()) return null;
  return bn;
};

/** 千分位數字格式,decimals 為小數位數 */
export function formatNumber(
  value: Numeric | null | undefined,
  decimals = 0,
  fallback = "-",
): string {
  if (value === null || value === undefined) return fallback;
  const bn = safeBn(value);
  if (!bn) return fallback;
  return bn.toFormat(decimals);
}

/** 百分比,輸入是「比例」(0.0825 → 8.25%) */
export function formatPercent(
  value: Numeric | null | undefined,
  decimals = 2,
  fallback = "-",
): string {
  if (value === null || value === undefined) return fallback;
  const bn = safeBn(value);
  if (!bn) return fallback;
  return `${bn.multipliedBy(100).toFormat(decimals)}%`;
}

/** 貨幣,decimals 預設 TW=0 / US=2 */
export function formatCurrency(
  value: Numeric | null | undefined,
  currency: "TWD" | "USD" = "TWD",
  decimalsOverride?: number,
  fallback = "-",
): string {
  if (value === null || value === undefined) return fallback;
  const bn = safeBn(value);
  if (!bn) return fallback;
  const decimals = decimalsOverride ?? (currency === "TWD" ? 0 : 2);
  const symbol = currency === "TWD" ? "NT$" : "US$";
  return `${symbol}${bn.toFormat(decimals)}`;
}

/** UTC ISO 字串 → 用戶時區顯示 */
export function formatDateTime(
  iso: string | null | undefined,
  userTz = "Asia/Taipei",
  pattern = "YYYY-MM-DD HH:mm:ss",
  fallback = "-",
): string {
  if (!iso) return fallback;
  const d = dayjs.utc(iso);
  if (!d.isValid()) return fallback;
  return d.tz(userTz).format(pattern);
}

/** 只顯示日期 */
export function formatDate(
  iso: string | null | undefined,
  userTz = "Asia/Taipei",
  fallback = "-",
): string {
  return formatDateTime(iso, userTz, "YYYY-MM-DD", fallback);
}

/** 相對時間(例如「3 分鐘前」) — 簡化版,只支援過去時間 */
export function formatRelative(
  iso: string | null | undefined,
  now: Date | string = new Date(),
  fallback = "-",
): string {
  if (!iso) return fallback;
  const d = dayjs.utc(iso);
  if (!d.isValid()) return fallback;
  const diffSec = dayjs.utc(now).diff(d, "second");
  if (diffSec < 0) return fallback;
  if (diffSec < 60) return `${diffSec} 秒前`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分鐘前`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小時前`;
  return `${Math.floor(diffSec / 86400)} 天前`;
}

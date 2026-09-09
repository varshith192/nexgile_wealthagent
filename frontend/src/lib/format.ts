/**
 * Formatting helpers.
 *
 * Financial figures are formatted in one place so a number never appears in two
 * different shapes on two different screens.
 *
 * Indian conventions throughout: the rupee symbol, the lakh/crore grouping
 * (₹12,34,567 rather than ₹1,234,567) and L/Cr abbreviations in compact form.
 */

const CURRENCY = "INR";
const LOCALE = "en-IN";

const LAKH = 1_00_000;
const CRORE = 1_00_00_000;

/**
 * Compact rupee amounts use the units Indian readers actually think in.
 * Below a lakh the full figure is short enough to show in full.
 */
function compactRupees(value: number, decimals = 2): string {
  const sign = value < 0 ? "-" : "";
  const amount = Math.abs(value);

  if (amount >= CRORE) {
    return `${sign}₹${(amount / CRORE).toFixed(decimals)} Cr`;
  }
  if (amount >= LAKH) {
    return `${sign}₹${(amount / LAKH).toFixed(decimals)} L`;
  }
  if (amount >= 1_000) {
    return `${sign}₹${(amount / 1_000).toFixed(1)} K`;
  }
  return `${sign}₹${amount.toFixed(0)}`;
}

export function formatCurrency(
  value: number | null | undefined,
  options: { compact?: boolean; decimals?: number; signed?: boolean } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const { compact = false, decimals, signed = false } = options;

  if (compact && Math.abs(value) >= 1_000) {
    const formatted = compactRupees(value, decimals ?? 2);
    return signed && value > 0 ? `+${formatted}` : formatted;
  }

  const formatter = new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: CURRENCY,
    maximumFractionDigits: decimals ?? (Math.abs(value) < 100 ? 2 : 0),
    minimumFractionDigits: decimals ?? 0,
  });

  const formatted = formatter.format(value);
  return signed && value > 0 ? `+${formatted}` : formatted;
}

/** Just the unit, for axis labels and dense tables. */
export function formatCompactRupees(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return compactRupees(value, decimals);
}

export function formatPercent(
  value: number | null | undefined,
  options: { decimals?: number; signed?: boolean } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const { decimals = 2, signed = false } = options;
  const formatted = `${(value * 100).toFixed(decimals)}%`;
  return signed && value > 0 ? `+${formatted}` : formatted;
}

export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value);
}

export function formatDate(value: string | Date | null | undefined, style: "short" | "medium" | "long" = "medium"): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  const options: Intl.DateTimeFormatOptions =
    style === "short"
      ? { day: "numeric", month: "short" }
      : style === "long"
        ? { day: "numeric", month: "long", year: "numeric" }
        : { day: "numeric", month: "short", year: "numeric" };
  return new Intl.DateTimeFormat(LOCALE, options).format(date);
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatRelative(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";

  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  for (const [unit, secondsInUnit] of units) {
    if (Math.abs(seconds) >= secondsInUnit) {
      return formatter.format(Math.round(seconds / secondsInUnit), unit);
    }
  }
  return "just now";
}

/** The Indian financial year runs 1 April to 31 March. */
export function financialYear(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  const start = date.getMonth() >= 3 ? date.getFullYear() : date.getFullYear() - 1;
  return `FY ${start}-${String(start + 1).slice(-2)}`;
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function initialsOf(name: string | null | undefined): string {
  if (!name) return "—";
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** Colour direction for a signed figure. Zero is deliberately neutral. */
export function trendTone(value: number | null | undefined): "positive" | "negative" | "neutral" {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

export function truncate(value: string, length = 90): string {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

/** en-ZA: day–month–year ordering, 24h; browser applies user's actual timezone for real instants. */

const LOCALE = "en-ZA";

export const DATE_TIME_DISPLAY: Intl.DateTimeFormatOptions = {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
};

const DATE_TIME_WITH_SECONDS: Intl.DateTimeFormatOptions = {
  ...DATE_TIME_DISPLAY,
  second: "2-digit",
};

/** True UTC / server timestamps: show in the user's local timezone. */
export function formatUserDateTime(value: string | null, withSeconds = false): string {
  if (!value) return "-";
  const opts = withSeconds ? DATE_TIME_WITH_SECONDS : DATE_TIME_DISPLAY;
  return new Date(value).toLocaleString(LOCALE, opts);
}

/** Calendar date from `YYYY-MM-DD` (e.g. backfill range), no time zone shift. */
export function formatUserDateOnly(isoDate: string): string {
  const parts = isoDate.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return isoDate;
  const [y, m, d] = parts;
  return new Date(y, m - 1, d).toLocaleDateString(LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Strava `start_date_local` is local wall clock at the activity, but the API and our DB often
 * attach `Z` or `+00:00`. Parsing as UTC shifts desktop users away from that wall time; strip the
 * marker so JS treats the string as local.
 */
export function formatStravaLocalDateTime(value: string | null): string {
  if (!value) return "-";
  const naive = stripStravaLocalUtcMarker(value);
  return new Date(naive).toLocaleString(LOCALE, DATE_TIME_DISPLAY);
}

function stripStravaLocalUtcMarker(iso: string): string {
  if (iso.endsWith("Z") || iso.endsWith("z")) {
    return iso.slice(0, -1);
  }
  if (iso.endsWith("+00:00")) {
    return iso.slice(0, -6);
  }
  return iso;
}

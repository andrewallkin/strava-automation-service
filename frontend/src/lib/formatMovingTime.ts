/** Total moving time from Strava (seconds), e.g. 1h 24m 34s, 45m 30s, 34s. */
export function formatMovingTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const r = s % 3600;
  const m = Math.floor(r / 60);
  const sec = r % 60;
  const parts: string[] = [];
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  if (sec) parts.push(`${sec}s`);
  if (parts.length === 0) parts.push("0s");
  return parts.join(" ");
}

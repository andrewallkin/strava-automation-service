import type { ActivityTypeSummary, ActivityTypeWeek, SportTypeTotals, StoredActivity } from "./api";
import { formatMovingTime } from "./formatMovingTime";

export const RUN_SPORT_TYPES: ReadonlySet<string> = new Set(["Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun"]);

const SPORT_ICONS: Record<string, string> = {
  Run: "🏃",
  TrailRun: "🏃",
  Walk: "🚶",
  Golf: "⛳",
  Padel: "🎾",
  Workout: "⏱",
  WeightTraining: "💪",
};

export function sportIcon(sportType: string | null): string {
  return (sportType && SPORT_ICONS[sportType]) || "•";
}

export function isRunSport(sportType: string | null): boolean {
  return sportType !== null && RUN_SPORT_TYPES.has(sportType);
}

export type Trend = "up" | "down" | "flat";

export type ActivityTypeRow = {
  sportType: string;
  thisWeek: SportTypeTotals | null;
  lastWeek: SportTypeTotals | null;
  trend: Trend;
};

function movingTime(totals: SportTypeTotals | null): number {
  return totals?.movingTimeSec ?? 0;
}

export function activityTypeRows(summary: ActivityTypeSummary): ActivityTypeRow[] {
  const current = summary.thisWeek.bySportType;
  const previous = summary.lastWeek.bySportType;
  const sportTypes = Array.from(new Set([...Object.keys(current), ...Object.keys(previous)]));
  return sportTypes
    .map((sportType): ActivityTypeRow => {
      const thisWeek = current[sportType] ?? null;
      const lastWeek = previous[sportType] ?? null;
      const delta = movingTime(thisWeek) - movingTime(lastWeek);
      return { sportType, thisWeek, lastWeek, trend: delta > 0 ? "up" : delta < 0 ? "down" : "flat" };
    })
    .sort(
      (a, b) =>
        movingTime(b.thisWeek) - movingTime(a.thisWeek) ||
        movingTime(b.lastWeek) - movingTime(a.lastWeek) ||
        a.sportType.localeCompare(b.sportType),
    );
}

export function weekTotals(week: ActivityTypeWeek): { activityCount: number; movingTimeSec: number } {
  return Object.values(week.bySportType).reduce(
    (sum, totals) => ({
      activityCount: sum.activityCount + totals.activityCount,
      movingTimeSec: sum.movingTimeSec + totals.movingTimeSec,
    }),
    { activityCount: 0, movingTimeSec: 0 },
  );
}

export function formatHoursMinutes(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

export function formatPace(secondsPerKm: number): string {
  const seconds = Math.round(secondsPerKm);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}/km`;
}

export function formatDistanceKm(distanceM: number): string {
  return `${(distanceM / 1000).toFixed(2)} km`;
}

export type CardFact = { key: string; text: string };

export function activityCardFacts(activity: StoredActivity, compact: boolean): CardFact[] {
  const facts: CardFact[] = [];
  if (activity.distanceM && activity.distanceM > 0) {
    facts.push({ key: "distance", text: formatDistanceKm(activity.distanceM) });
  }
  if (activity.movingTimeSec != null) {
    facts.push({ key: "moving", text: `⏱ ${formatMovingTime(activity.movingTimeSec)}` });
  }
  if (!compact && activity.elapsedTimeSec != null) {
    facts.push({ key: "elapsed", text: `elapsed ${formatMovingTime(activity.elapsedTimeSec)}` });
  }
  if (isRunSport(activity.sportType) && activity.averagePaceSecPerKm != null) {
    facts.push({ key: "pace", text: formatPace(activity.averagePaceSecPerKm) });
  }
  if (!compact && activity.elevationGainM && activity.elevationGainM > 0) {
    facts.push({ key: "elevation", text: `⛰ ${Math.round(activity.elevationGainM)}m` });
  }
  if (activity.averageHeartrate != null) {
    facts.push({ key: "heartrate", text: `♥ ${Math.round(activity.averageHeartrate)}` });
  }
  return facts;
}

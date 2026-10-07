import { useEffect, useState } from "react";
import {
  EventRow,
  GymCalendar,
  PendingActivity,
  ShoeVaultEntry,
  StravaActivity,
  StreakData,
  Summary,
  WeeklySummary,
  fetchActivities,
  fetchEvents,
  fetchGymCalendar,
  fetchPending,
  fetchShoeVault,
  fetchStreak,
  fetchSummary,
  fetchWeeklySummary,
  retryActivity
} from "../lib/api";
import { formatMovingTime } from "../lib/formatMovingTime";
import { formatStravaLocalDateTime, formatUserDateTime } from "../lib/datetimeDisplay";

function formatEventType(eventType: string): string {
  return eventType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  const classes: Record<string, string> = {
    ok: "bg-green-100 text-green-700",
    error: "bg-red-100 text-red-700",
    retry: "bg-yellow-100 text-yellow-700"
  };
  const cls = classes[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

const RUN_TYPES = new Set(["Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun"]);

function formatPace(distanceM: number, movingTimeS: number): string {
  if (!distanceM || !movingTimeS) return "";
  const km = distanceM / 1000;
  const paceSecPerKm = movingTimeS / km;
  const paceMin = Math.floor(paceSecPerKm / 60);
  const paceSec = Math.floor(paceSecPerKm % 60);
  return `${paceMin}:${String(paceSec).padStart(2, "0")}/km`;
}

function ActivityCard({ activity }: { activity: StravaActivity }) {
  const isRun = RUN_TYPES.has(activity.type ?? "");
  const distanceKm = activity.distance ? (activity.distance / 1000).toFixed(2) : null;
  const duration = activity.moving_time != null ? formatMovingTime(activity.moving_time) : null;
  const pace = (activity.distance && activity.moving_time)
    ? formatPace(activity.distance, activity.moving_time)
    : null;
  const elevation = activity.total_elevation_gain && activity.total_elevation_gain > 0
    ? Math.round(activity.total_elevation_gain)
    : null;

  return (
    <div className={`flex gap-4 px-5 py-4 hover:bg-gray-50 transition-colors border-l-4 ${isRun ? "border-orange-400" : "border-gray-300"}`}>
      <div className="text-2xl leading-none mt-0.5">{isRun ? "🏃" : "💪"}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-gray-900 truncate">
            {activity.name ?? (isRun ? "Run" : "Workout")}
          </p>
          <p className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">
            {activity.start_date_local ? formatStravaLocalDateTime(activity.start_date_local) : ""}
          </p>
        </div>
        {isRun && (distanceKm || duration) && (
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-500">
            {distanceKm && <span className="font-medium text-gray-700">{distanceKm} km</span>}
            {duration && <span>{duration}</span>}
            {pace && <span>{pace}</span>}
            {elevation && <span>⛰ {elevation}m</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function ActivityFeedSkeleton() {
  return (
    <div className="divide-y divide-gray-100">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex gap-4 px-5 py-4 border-l-4 border-gray-100">
          <div className="h-6 w-6 bg-gray-200 rounded animate-pulse" />
          <div className="flex-1 space-y-2">
            <div className="h-3 bg-gray-200 rounded w-2/3 animate-pulse" />
            <div className="h-3 bg-gray-200 rounded w-1/3 animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

const ACTIVITIES_PAGE_SIZE = 15;

export function ActivityFeed() {
  const [activities, setActivities] = useState<StravaActivity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    fetchActivities(1)
      .then((data) => {
        setActivities(data);
        setPage(1);
        setHasMore(data.length >= ACTIVITIES_PAGE_SIZE);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  async function loadMore() {
    if (loadingMore || !hasMore || activities === null) return;
    setLoadingMore(true);
    try {
      const nextPage = page + 1;
      const data = await fetchActivities(nextPage);
      setActivities((prev) => (prev ? [...prev, ...data] : data));
      setPage(nextPage);
      setHasMore(data.length >= ACTIVITIES_PAGE_SIZE);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Activity Feed</h2>
        <p className="text-xs text-gray-500 mt-0.5">Recent runs &amp; gym sessions</p>
      </div>
      {error ? (
        <p className="px-5 py-4 text-sm text-red-600">{error}</p>
      ) : activities === null ? (
        <ActivityFeedSkeleton />
      ) : activities.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No activities yet.</p>
      ) : (
        <>
          <div className="divide-y divide-gray-100">
            {activities.map((a) => (
              <ActivityCard key={a.id} activity={a} />
            ))}
          </div>
          {hasMore && (
            <div className="px-5 py-4 border-t border-gray-100">
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="w-full py-2 text-sm font-medium text-orange-600 hover:text-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loadingMore ? "Loading…" : "View more"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function StatsGrid({ summary, className }: { summary: Summary | null; className?: string }) {
  const card = "bg-white rounded-xl shadow-sm border border-gray-200 px-4 py-3 flex flex-col justify-center";
  return (
    <div className={`grid grid-cols-2 grid-rows-2 gap-3${className ? ` ${className}` : ""}`}>
      <div className={card}>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Pending</p>
        <p className="mt-1 text-2xl font-bold text-gray-900">{summary?.pending_count ?? "-"}</p>
      </div>
      <div className={card}>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Runs updated</p>
        <p className="mt-1 text-2xl font-bold text-orange-500">{summary?.runs_updated ?? "-"}</p>
      </div>
      <div className={card}>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Gym hidden</p>
        <p className="mt-1 text-2xl font-bold text-gray-900">{summary?.gym_hidden ?? "-"}</p>
      </div>
      <div
        className={card}
        title="When the automation last processed something (webhook, run update, gym hide, etc.)"
      >
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Last automation</p>
        <p className="mt-1 text-xs font-semibold text-gray-900 leading-tight">
          {formatUserDateTime(summary?.last_event_at ?? null)}
        </p>
      </div>
    </div>
  );
}

export function PendingActivities({
  pending,
  onRetry
}: {
  pending: PendingActivity[];
  onRetry: (id: number) => Promise<void>;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-900">Pending Activities</h2>
      </div>
      {pending.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No pending activities.</p>
      ) : (
        <div className="divide-y divide-gray-100">
          {pending.map((item) => (
            <div key={item.activity_id} className="px-5 py-3 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-gray-900">Activity #{item.activity_id}</p>
                <p className="text-xs text-gray-500">{formatUserDateTime(item.created_at)}</p>
              </div>
              <button
                type="button"
                onClick={() => onRetry(item.activity_id)}
                className="flex-shrink-0 px-3 py-1.5 text-sm font-medium bg-orange-500 hover:bg-orange-600 text-white rounded-md transition-colors"
              >
                Retry
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function RecentEvents({ events }: { events: EventRow[] }) {
  return (
    <details className="group bg-white rounded-xl shadow-sm border border-gray-200">
      <summary className="px-5 py-4 cursor-pointer list-none flex items-center justify-between select-none">
        <span className="text-sm font-semibold text-gray-700">Recent Events</span>
        <svg
          className="h-4 w-4 text-gray-400 transition-transform group-open:rotate-180"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      {events.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500 border-t border-gray-100">No events yet.</p>
      ) : (
        <div className="overflow-x-auto border-t border-gray-100">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">Time</th>
                <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">Type</th>
                <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {events.map((event) => (
                <tr key={event.id} className="hover:bg-gray-50 text-gray-600">
                  <td className="px-5 py-2 whitespace-nowrap">{formatUserDateTime(event.created_at)}</td>
                  <td className="px-5 py-2 whitespace-nowrap">{formatEventType(event.event_type)}</td>
                  <td className="px-5 py-2"><StatusBadge status={event.status} /></td>
                  <td className="px-5 py-2">{event.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}

export function ErrorCard({ message, className }: { message: string; className?: string }) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-red-200 px-5 py-4${className ? ` ${className}` : ""}`}>
      <p className="text-sm text-red-600">{message}</p>
    </div>
  );
}

export function ShoeVault({ className }: { className?: string }) {
  const [shoes, setShoes] = useState<ShoeVaultEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchShoeVault()
      .then(setShoes)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load shoes"));
  }, []);

  if (error) return <ErrorCard message={error} />;

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200${className ? ` ${className}` : ""}`}>
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Shoe Vault</h2>
        <p className="text-xs text-gray-500 mt-0.5">Lifetime distance per shoe</p>
      </div>
      {shoes === null ? (
        <div className="px-5 py-4 space-y-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-3 bg-gray-200 rounded w-2/3 animate-pulse" />
              <div className="h-2 bg-gray-200 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : shoes.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No shoes found.</p>
      ) : (
        <div className="divide-y divide-gray-100">
          {shoes.map((shoe) => {
            const km = Math.round(shoe.total_distance_m / 1000);
            const pct = Math.min(km / 800, 1) * 100;
            const nearRetirement = km >= 700;
            return (
              <div key={shoe.strava_gear_id} className="px-5 py-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-medium text-gray-900 truncate">{shoe.name}</span>
                  {nearRetirement && (
                    <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                      near retirement
                    </span>
                  )}
                  <span className="ml-auto flex-shrink-0 text-xs text-gray-500">{km} km</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${nearRetirement ? "bg-red-500" : "bg-orange-400"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatRunPace(km: number, seconds: number): string {
  if (!km || !seconds) return "";
  const paceSecPerKm = seconds / km;
  const paceMin = Math.floor(paceSecPerKm / 60);
  const paceSec = Math.floor(paceSecPerKm % 60);
  return `${paceMin}:${String(paceSec).padStart(2, "0")}/km`;
}

export function WeeklyTrainingSummary({ className }: { className?: string }) {
  const [data, setData] = useState<WeeklySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWeeklySummary()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load weekly summary"));
  }, []);

  if (error) return <ErrorCard message={error} />;

  const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];
  const FULL_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

  function Trend({ thisVal, lastVal }: { thisVal: number; lastVal: number }) {
    if (thisVal > lastVal) return <span className="text-green-500 text-xs">↑</span>;
    if (thisVal < lastVal) return <span className="text-red-500 text-xs">↓</span>;
    return <span className="text-gray-400 text-xs">—</span>;
  }

  const maxKm = data ? Math.max(...data.this_week.days.map((d) => d.km), 0.1) : 1;

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200${className ? ` ${className}` : ""}`}>
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">🏃 Weekly Running</h2>
        <p className="text-xs text-gray-500 mt-0.5">This week vs last week</p>
      </div>
      {data === null ? (
        <div className="px-5 py-4 space-y-3">
          <div className="h-3 bg-gray-200 rounded w-full animate-pulse" />
          <div className="h-10 bg-gray-100 rounded animate-pulse" />
        </div>
      ) : (
        <div className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-xs text-gray-500">📏 km</p>
              <div className="flex items-center justify-center gap-1">
                <p className="text-lg font-bold text-gray-900">{data.this_week.total_km.toFixed(1)}</p>
                <Trend thisVal={data.this_week.total_km} lastVal={data.last_week.total_km} />
              </div>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500">🏅 runs</p>
              <div className="flex items-center justify-center gap-1">
                <p className="text-lg font-bold text-gray-900">{data.this_week.run_count}</p>
                <Trend thisVal={data.this_week.run_count} lastVal={data.last_week.run_count} />
              </div>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500">⛰️ elev</p>
              <div className="flex items-center justify-center gap-1">
                <p className="text-lg font-bold text-gray-900">{data.this_week.elevation_m}m</p>
                <Trend thisVal={data.this_week.elevation_m} lastVal={data.last_week.elevation_m} />
              </div>
            </div>
          </div>

          {/* Bar chart */}
          <div>
            <div className="flex items-end gap-1 h-16">
              {data.this_week.days.map((day, i) => (
                <div key={i} className="flex-1 flex flex-col items-center justify-end">
                  {day.km > 0 && (
                    <span className="text-[10px] text-gray-500 mb-0.5">{day.km.toFixed(1)}</span>
                  )}
                  <div
                    className="w-full bg-orange-400 rounded-t"
                    style={{ height: `${day.km > 0 ? Math.max((day.km / maxKm) * 40, 3) : 0}px` }}
                  />
                </div>
              ))}
            </div>
            <div className="flex gap-1 mt-1">
              {DAY_LABELS.map((l, i) => (
                <div key={i} className="flex-1 text-center text-xs text-gray-400">{l}</div>
              ))}
            </div>
          </div>

          {/* Per-day activity details */}
          {data.this_week.days.some((d) => d.count > 0) && (
            <div className="pt-1 border-t border-gray-100">
              {/* Column headers */}
              <div className="grid grid-cols-[5rem_1fr_3.5rem_minmax(6.25rem,max-content)_4rem_3rem] gap-x-2 px-1 pb-1 text-[10px] font-medium text-gray-400 uppercase tracking-wide">
                <span>Day</span>
                <span>Activity</span>
                <span className="text-right">📏 km</span>
                <span className="text-right whitespace-nowrap">⏱ time</span>
                <span className="text-right">⚡ pace</span>
                <span className="text-right">⛰ elev</span>
              </div>
              <div className="space-y-1">
                {data.this_week.days.map((day, i) =>
                  day.activities.map((act, j) => (
                    <div
                      key={`${i}-${j}`}
                      className="grid grid-cols-[5rem_1fr_3.5rem_minmax(6.25rem,max-content)_4rem_3rem] gap-x-2 items-center px-1 py-1 rounded-lg bg-gray-50 text-xs"
                    >
                      <span className="text-gray-400 font-medium">{FULL_DAY_NAMES[i]}</span>
                      <span className="text-gray-900 font-medium truncate">{act.name}</span>
                      <span className="text-right text-orange-600 font-semibold">{act.km.toFixed(1)}</span>
                      <span className="text-right text-gray-600 whitespace-nowrap tabular-nums">
                        {formatMovingTime(act.moving_time_s)}
                      </span>
                      <span className="text-right text-blue-600 font-medium">{formatRunPace(act.km, act.moving_time_s)}</span>
                      <span className="text-right text-gray-500">{act.elevation_m > 0 ? `${act.elevation_m}m` : "—"}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function RunningStreak() {
  const [data, setData] = useState<StreakData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStreak()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load streak"));
  }, []);

  if (error) return <ErrorCard message={error} />;

  function formatPaceSec(secPerKm: number): string {
    const min = Math.floor(secPerKm / 60);
    const sec = Math.floor(secPerKm % 60);
    return `${min}:${String(sec).padStart(2, "0")}/km`;
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Running Streak &amp; PRs</h2>
        <p className="text-xs text-gray-500 mt-0.5">Last 90 days</p>
      </div>
      {data === null ? (
        <div className="px-5 py-4 space-y-3">
          <div className="h-12 bg-gray-100 rounded animate-pulse" />
          <div className="h-12 bg-gray-100 rounded animate-pulse" />
        </div>
      ) : (
        <div className="px-5 py-4 space-y-4">
          <div className="flex gap-3">
            <div className="flex-1 bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 text-center">
              <p className="text-2xl font-bold text-orange-600">{data.current_streak}</p>
              <p className="text-xs text-orange-500 mt-0.5">current streak (days)</p>
            </div>
            <div className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-center">
              <p className="text-2xl font-bold text-gray-700">{data.best_streak}</p>
              <p className="text-xs text-gray-500 mt-0.5">best streak (days)</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {data.prs.fastest_pace && (
              <div className="bg-gray-50 rounded-lg px-3 py-3">
                <p className="text-xs text-gray-500 mb-1">Fastest pace</p>
                <p className="text-sm font-bold text-gray-900">
                  {data.prs.fastest_pace.value_sec_per_km != null
                    ? formatPaceSec(data.prs.fastest_pace.value_sec_per_km)
                    : "—"}
                </p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">
                  {data.prs.fastest_pace.activity_name ?? "Run"}
                </p>
              </div>
            )}
            {data.prs.longest_run && (
              <div className="bg-gray-50 rounded-lg px-3 py-3">
                <p className="text-xs text-gray-500 mb-1">Longest run</p>
                <p className="text-sm font-bold text-gray-900">
                  {(data.prs.longest_run.distance_m / 1000).toFixed(2)} km
                </p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">
                  {data.prs.longest_run.activity_name ?? "Run"}
                </p>
              </div>
            )}
            {data.prs.most_elevation && (
              <div className="bg-gray-50 rounded-lg px-3 py-3">
                <p className="text-xs text-gray-500 mb-1">Most elevation</p>
                <p className="text-sm font-bold text-gray-900">
                  {data.prs.most_elevation.elevation_m != null
                    ? `${Math.round(data.prs.most_elevation.elevation_m)}m`
                    : "—"}
                </p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">
                  {data.prs.most_elevation.activity_name ?? "Run"}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function GymConsistencyCalendar() {
  const [data, setData] = useState<GymCalendar | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGymCalendar()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load gym calendar"));
  }, []);

  if (error) return <ErrorCard message={error} />;

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];

  function buildCalendar(year: number, month: number, gymDays: Set<string>) {
    const firstDay = new Date(year, month - 1, 1);
    // Shift so Mon=0
    const offset = (firstDay.getDay() + 6) % 7;
    const daysInMonth = new Date(year, month, 0).getDate();
    return { offset, daysInMonth };
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Gym Consistency</h2>
        <p className="text-xs text-gray-500 mt-0.5">Last 60 days</p>
      </div>
      {data === null ? (
        <div className="px-5 py-4">
          <div className="h-32 bg-gray-100 rounded animate-pulse" />
        </div>
      ) : (
        <div className="px-5 py-4 space-y-4">
          <div className="flex gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-orange-500">{data.month_session_count}</p>
              <p className="text-xs text-gray-500">sessions this month</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-700">{data.weeks_with_gym_streak}</p>
              <p className="text-xs text-gray-500">week streak</p>
            </div>
          </div>
          {(() => {
            const gymSet = new Set(data.gym_days);
            const { offset, daysInMonth } = buildCalendar(data.year, data.month, gymSet);
            const cells: (number | null)[] = [
              ...Array(offset).fill(null),
              ...Array.from({ length: daysInMonth }, (_, i) => i + 1)
            ];
            return (
              <div>
                <div className="grid grid-cols-7 gap-1 mb-1">
                  {DAY_LABELS.map((l, i) => (
                    <div key={i} className="text-center text-xs text-gray-400">{l}</div>
                  ))}
                </div>
                <div className="grid grid-cols-7 gap-1">
                  {cells.map((day, i) => {
                    if (day === null) return <div key={i} />;
                    const dateStr = `${data.year}-${String(data.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                    const isGym = gymSet.has(dateStr);
                    const isToday = dateStr === todayStr;
                    return (
                      <div key={i} className="flex items-center justify-center aspect-square">
                        <div
                          className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-medium
                            ${isGym ? "bg-orange-400 text-white" : "text-gray-600"}
                            ${isToday && !isGym ? "ring-2 ring-orange-400" : ""}
                          `}
                        >
                          {day}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

// Legacy standalone Dashboard (kept for compatibility)
export function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [pending, setPending] = useState<PendingActivity[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load(): Promise<void> {
    try {
      const [s, p, e] = await Promise.all([fetchSummary(), fetchPending(), fetchEvents()]);
      setSummary(s);
      setPending(p);
      setEvents(e);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
    const t = window.setInterval(load, 5000);
    return () => window.clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Strava <span className="text-orange-500">Dashboard</span>
        </h1>
        {error && (
          <div className="rounded-lg px-4 py-3 text-sm font-medium bg-red-50 text-red-700 border border-red-200">
            Error: {error}
          </div>
        )}
        <StatsGrid summary={summary} />
        <PendingActivities pending={pending} onRetry={retryActivity} />
        <RecentEvents events={events} />
      </main>
    </div>
  );
}

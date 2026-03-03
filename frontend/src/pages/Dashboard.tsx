import { useEffect, useState } from "react";
import {
  EventRow,
  PendingActivity,
  StravaActivity,
  Summary,
  fetchActivities,
  fetchEvents,
  fetchPending,
  fetchSummary,
  retryActivity
} from "../lib/api";

const DATE_OPTS: Intl.DateTimeFormatOptions = {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
};

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-ZA", DATE_OPTS);
}

/** Strava start_date_local is local time but API incorrectly adds Z. Strip Z so JS parses as local. */
function formatLocalDate(value: string | null): string {
  if (!value) return "-";
  const localStr = value.replace(/Z$/i, "");
  return new Date(localStr).toLocaleString("en-ZA", DATE_OPTS);
}

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

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins >= 60) {
    const hrs = Math.floor(mins / 60);
    const rem = mins % 60;
    return `${hrs}h ${String(rem).padStart(2, "0")}m`;
  }
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function ActivityCard({ activity }: { activity: StravaActivity }) {
  const isRun = RUN_TYPES.has(activity.type ?? "");
  const distanceKm = activity.distance ? (activity.distance / 1000).toFixed(2) : null;
  const duration = activity.moving_time ? formatDuration(activity.moving_time) : null;
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
            {activity.start_date_local ? formatLocalDate(activity.start_date_local) : ""}
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

export function StatsGrid({ summary }: { summary: Summary | null }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-4 py-3">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Pending</p>
        <p className="mt-1 text-2xl font-bold text-gray-900">{summary?.pending_count ?? "-"}</p>
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-4 py-3">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Runs updated</p>
        <p className="mt-1 text-2xl font-bold text-orange-500">{summary?.runs_updated ?? "-"}</p>
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-4 py-3">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Gym hidden</p>
        <p className="mt-1 text-2xl font-bold text-gray-900">{summary?.gym_hidden ?? "-"}</p>
      </div>
      <div
        className="bg-white rounded-xl shadow-sm border border-gray-200 px-4 py-3"
        title="When the automation last processed something (webhook, run update, gym hide, etc.)"
      >
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Last automation</p>
        <p className="mt-1 text-xs font-semibold text-gray-900 leading-tight">
          {formatDate(summary?.last_event_at ?? null)}
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
                <p className="text-xs text-gray-500">{formatDate(item.created_at)}</p>
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
                  <td className="px-5 py-2 whitespace-nowrap">{formatDate(event.created_at)}</td>
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

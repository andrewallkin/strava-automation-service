import { useEffect, useState } from "react";
import { EventRow, PendingActivity, Summary, fetchEvents, fetchPending, fetchSummary, retryActivity } from "../lib/api";

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
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

type DashboardEmbedProps = {
  summary: Summary | null;
  pending: PendingActivity[];
  events: EventRow[];
  onRetry: (activityId: number) => Promise<void>;
  onRefresh: () => Promise<void>;
};

export function DashboardEmbed({ summary, pending, events, onRetry, onRefresh }: DashboardEmbedProps) {
  useEffect(() => {
    const t = window.setInterval(onRefresh, 5000);
    return () => window.clearInterval(t);
  }, [onRefresh]);

  return (
    <div className="space-y-6">
      {/* Stats summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-5 py-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Pending</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {summary?.pending_count ?? "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-5 py-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Runs updated</p>
          <p className="mt-1 text-2xl font-bold text-orange-500">
            {summary?.runs_updated ?? "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-5 py-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Gym hidden</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {summary?.gym_hidden ?? "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-5 py-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Last event</p>
          <p className="mt-1 text-sm font-semibold text-gray-900">
            {formatDate(summary?.last_event_at ?? null)}
          </p>
        </div>
      </div>

      {/* Pending activities */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Pending Activities</h2>
        </div>
        {pending.length === 0 ? (
          <p className="px-6 py-4 text-sm text-gray-500">No pending activities.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {pending.map((item) => (
              <div key={item.activity_id} className="px-6 py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">Activity #{item.activity_id}</p>
                  <p className="text-xs text-gray-500">Created {formatDate(item.created_at)}</p>
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

      {/* Events table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Recent Events</h2>
        </div>
        {events.length === 0 ? (
          <p className="px-6 py-4 text-sm text-gray-500">No events yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Time
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Message
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {events.map((event) => (
                  <tr key={event.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {formatDate(event.created_at)}
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-900 whitespace-nowrap">
                      {formatEventType(event.event_type)}
                    </td>
                    <td className="px-6 py-3">
                      <StatusBadge status={event.status} />
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-600">
                      {event.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

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
        <DashboardEmbed summary={summary} pending={pending} events={events} onRetry={retryActivity} onRefresh={load} />
      </main>
    </div>
  );
}

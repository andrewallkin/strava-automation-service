import { useCallback, useState } from "react";
import { EventRow, fetchEvents } from "../lib/api";
import { formatUserDateTime } from "../lib/datetimeDisplay";
import { usePolling } from "../lib/usePolling";

function formatEventType(eventType: string): string {
  return eventType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  const classes: Record<string, string> = {
    ok: "bg-green-100 text-green-700",
    error: "bg-red-100 text-red-700",
    retry: "bg-yellow-100 text-yellow-700",
  };
  const cls = classes[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export function EventsPage() {
  const [events, setEvents] = useState<EventRow[] | null>(null);

  const load = useCallback(async () => {
    try {
      setEvents(await fetchEvents());
    } catch {
      // ignore
    }
  }, []);

  usePolling(load, 5000);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Events</h2>
        <p className="text-xs text-gray-500 mt-0.5">Automation event log</p>
      </div>
      {events === null ? (
        <div className="px-5 py-4 space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-4 bg-gray-200 rounded animate-pulse" />
          ))}
        </div>
      ) : events.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No events yet.</p>
      ) : (
        <div className="overflow-x-auto">
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
    </div>
  );
}

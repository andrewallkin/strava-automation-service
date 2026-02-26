import { useCallback, useEffect, useState } from "react";
import {
  EventRow,
  PendingActivity,
  Status,
  Summary,
  disconnectStrava,
  fetchEvents,
  fetchPending,
  fetchSummary,
  retryActivity,
  updateSettings
} from "../lib/api";
import { ActivityFeed, PendingActivities, RecentEvents, StatsGrid } from "./Dashboard";

function Toggle({
  checked,
  onChange,
  id
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  id: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      id={id}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 ${
        checked ? "bg-orange-500" : "bg-gray-200"
      }`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

type SettingsProps = {
  status: Status;
  onStatusChange: (s: Status | null) => void;
};

export function Settings({ status, onStatusChange }: SettingsProps) {
  const [localStatus, setLocalStatus] = useState<Status>(status);
  const [message, setMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [pending, setPending] = useState<PendingActivity[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);

  // Sync incoming status changes (e.g. after reconnect)
  useEffect(() => {
    setLocalStatus(status);
  }, [status]);

  // Handle ?strava=connected message on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      setMessage("Strava connected successfully.");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const [s, p, e] = await Promise.all([fetchSummary(), fetchPending(), fetchEvents()]);
      setSummary(s);
      setPending(p);
      setEvents(e);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadDashboard();
    const t = window.setInterval(loadDashboard, 5000);
    return () => window.clearInterval(t);
  }, [loadDashboard]);

  const handleToggle = async (key: "run_shoe_enabled" | "gym_hide_enabled", value: boolean) => {
    try {
      const updated = await updateSettings({ [key]: value });
      const next = { ...localStatus, ...updated };
      setLocalStatus(next);
      onStatusChange(next);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update");
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectStrava();
      onStatusChange(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to disconnect");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          {/* Left: logo + branding */}
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="" className="h-8 w-8 object-contain" aria-hidden="true" />
            <span className="text-lg font-bold text-gray-900">
              Strava <span className="text-orange-500">Automation</span>
            </span>
          </div>

          {/* Right: profile pic, name, disconnect */}
          <div className="flex items-center gap-3">
            {localStatus.athlete_profile_url && (
              <img
                src={localStatus.athlete_profile_url}
                alt="Profile"
                className="h-8 w-8 rounded-full object-cover border border-gray-200"
              />
            )}
            {localStatus.athlete_name && (
              <span className="hidden sm:block text-sm font-medium text-gray-700">
                {localStatus.athlete_name}
              </span>
            )}
            <button
              type="button"
              onClick={handleDisconnect}
              className="text-sm px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors"
            >
              Disconnect
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {/* Status message */}
        {message && (
          <div
            role="alert"
            className={`mb-4 rounded-lg px-4 py-3 text-sm font-medium ${
              message.startsWith("Error")
                ? "bg-red-50 text-red-700 border border-red-200"
                : "bg-green-50 text-green-700 border border-green-200"
            }`}
          >
            {message}
          </div>
        )}

        {/* Two-column layout */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left sidebar */}
          <div className="w-full lg:w-80 flex-shrink-0 space-y-4">
            {/* Automations card */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 divide-y divide-gray-100">
              <div className="px-5 py-4">
                <h2 className="text-sm font-semibold text-gray-900">Automations</h2>
              </div>

              <div className="px-5 py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">Run shoe selection</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Ask via Telegram which shoes you used after a run.
                  </p>
                </div>
                <Toggle
                  id="run-shoe-toggle"
                  checked={localStatus.run_shoe_enabled}
                  onChange={(val) => handleToggle("run_shoe_enabled", val)}
                />
              </div>

              <div className="px-5 py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">Gym hide from home</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Auto-hide strength workouts from your Strava feed.
                  </p>
                </div>
                <Toggle
                  id="gym-hide-toggle"
                  checked={localStatus.gym_hide_enabled}
                  onChange={(val) => handleToggle("gym_hide_enabled", val)}
                />
              </div>
            </div>

            {/* Stats grid */}
            <StatsGrid summary={summary} />

            {/* Pending activities */}
            <PendingActivities pending={pending} onRetry={retryActivity} />
          </div>

          {/* Right main area */}
          <div className="flex-1 min-w-0 space-y-4">
            <ActivityFeed />
            <RecentEvents events={events} />
          </div>
        </div>
      </main>
    </div>
  );
}

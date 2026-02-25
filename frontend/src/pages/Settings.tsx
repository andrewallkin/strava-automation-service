import { useCallback, useEffect, useState } from "react";
import {
  EventRow,
  PendingActivity,
  Status,
  Summary,
  disconnectStrava,
  fetchEvents,
  fetchPending,
  fetchStatus,
  fetchSummary,
  retryActivity,
  updateSettings
} from "../lib/api";
import { DashboardEmbed } from "./Dashboard";

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

export function Settings() {
  const [status, setStatus] = useState<Status | null | "loading">("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [pending, setPending] = useState<PendingActivity[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);

  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchStatus();
      setStatus(s ?? null);
    } catch {
      setStatus(null);
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
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const strava = params.get("strava");
    if (strava === "connected") {
      setMessage("Strava connected successfully.");
      loadStatus();
      window.history.replaceState({}, "", window.location.pathname);
    } else if (strava === "error") {
      setMessage(`Error: ${params.get("message") ?? "Unknown error"}`);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [loadStatus]);

  useEffect(() => {
    if (status && status !== "loading") {
      loadDashboard();
    }
  }, [status, loadDashboard]);

  const handleToggle = async (key: "run_shoe_enabled" | "gym_hide_enabled", value: boolean) => {
    if (status === null || status === "loading") return;
    try {
      const updated = await updateSettings({ [key]: value });
      setStatus((prev) => (prev && prev !== "loading" ? { ...prev, ...updated } : prev));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update");
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectStrava();
      setMessage(null);
      await loadStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to disconnect");
    }
  };

  const isConnected = status !== null && status !== "loading" && status.connected;

  return (
    <>
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-gray-900">Strava</span>
            <span className="text-xl font-bold text-orange-500">Automation</span>
          </div>
          <div className="flex items-center gap-3">
            {status !== "loading" && (
              <>
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${isConnected ? "bg-green-500" : "bg-gray-300"}`}
                />
                <span className="text-sm text-gray-600">
                  {isConnected
                    ? `Athlete #${status.strava_athlete_id}`
                    : "Not connected"}
                </span>
                {isConnected && (
                  <button
                    type="button"
                    onClick={handleDisconnect}
                    className="text-sm px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors"
                  >
                    Disconnect
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Status message */}
        {message && (
          <div
            role="alert"
            className={`rounded-lg px-4 py-3 text-sm font-medium ${
              message.startsWith("Error")
                ? "bg-red-50 text-red-700 border border-red-200"
                : "bg-green-50 text-green-700 border border-green-200"
            }`}
          >
            {message}
          </div>
        )}

        {status === "loading" ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-gray-500">Loading...</p>
          </div>
        ) : !isConnected ? (
          /* Not connected — connect card */
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Connect with Strava</h2>
            <p className="text-gray-500 mb-6 max-w-sm mx-auto">
              Link your Strava account to enable automatic shoe selection and activity
              privacy automations via Telegram.
            </p>
            <a
              href="/api/auth/strava/connect"
              className="inline-block px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white font-semibold rounded-lg transition-colors"
            >
              Connect with Strava
            </a>
          </div>
        ) : (
          /* Connected — settings card */
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 divide-y divide-gray-100">
            <div className="px-6 py-4">
              <h2 className="text-lg font-semibold text-gray-900">Automations</h2>
            </div>

            <div className="px-6 py-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-gray-900">Run shoe selection</p>
                <p className="text-sm text-gray-500">
                  When a run finishes, ask via Telegram which shoes you used.
                </p>
              </div>
              <Toggle
                id="run-shoe-toggle"
                checked={status.run_shoe_enabled}
                onChange={(val) => handleToggle("run_shoe_enabled", val)}
              />
            </div>

            <div className="px-6 py-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-gray-900">Gym hide from home</p>
                <p className="text-sm text-gray-500">
                  Automatically hide strength workouts from your Strava feed.
                </p>
              </div>
              <Toggle
                id="gym-hide-toggle"
                checked={status.gym_hide_enabled}
                onChange={(val) => handleToggle("gym_hide_enabled", val)}
              />
            </div>
          </div>
        )}

        {/* Dashboard — always shown when connected */}
        {isConnected && (
          <DashboardEmbed
            summary={summary}
            pending={pending}
            events={events}
            onRetry={retryActivity}
            onRefresh={loadDashboard}
          />
        )}
      </main>
    </>
  );
}

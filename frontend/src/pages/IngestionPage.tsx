import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  BackfillJob,
  BackfillRun,
  IngestedActivitiesResponse,
  cancelBackfill,
  cleanupIngestedActivities,
  createBackfill,
  fetchBackfill,
  fetchBackfillHistory,
  fetchBackfillJobs,
  fetchIngestedActivities,
  fetchLatestBackfill,
  retryFailedBackfill,
} from "../lib/api";

const activeStatuses = new Set(["created", "discovering", "queued", "running", "rate_limited"]);

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDateOnly(value: string): string {
  return value;
}

function formatDistance(value: number | null): string {
  if (!value) return "-";
  return `${(value / 1000).toFixed(2)} km`;
}

function formatDuration(value: number | null): string {
  if (!value) return "-";
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatRateLimitWait(run: BackfillRun): string | null {
  if (run.status !== "rate_limited") return null;
  if (!run.rate_limit_wait_until) return "Waiting for Strava rate limit reset.";
  const waitUntil = new Date(run.rate_limit_wait_until);
  const seconds = Math.max(0, Math.ceil((waitUntil.getTime() - Date.now()) / 1000));
  const minutes = Math.ceil(seconds / 60);
  return `Waiting for Strava ${run.rate_limit_wait_reason ?? "rate limit"} reset at ${formatDate(run.rate_limit_wait_until)} (${minutes} min).`;
}

function backfillProgress(run: BackfillRun): string {
  const total = run.missing_count || 0;
  const done = run.succeeded_count + run.failed_count + run.skipped_count;
  return total ? `${done}/${total}` : "-";
}

function StatusBadge({ status }: { status: string }) {
  const classes: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    succeeded: "bg-green-100 text-green-700",
    completed_with_errors: "bg-yellow-100 text-yellow-700",
    running: "bg-blue-100 text-blue-700",
    rate_limited: "bg-orange-100 text-orange-700",
    queued: "bg-gray-100 text-gray-700",
    discovering: "bg-blue-100 text-blue-700",
    failed: "bg-red-100 text-red-700",
    cancelled: "bg-gray-200 text-gray-700",
    skipped: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${classes[status] ?? "bg-gray-100 text-gray-700"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function DataFlags({ activity }: { activity: IngestedActivitiesResponse["items"][number] }) {
  const flags: Array<[string, boolean]> = [
    ["laps", activity.has_laps],
    ["splits", activity.has_splits],
    ["segments", activity.has_segments],
    ["efforts", activity.has_best_efforts],
    ["zones", activity.has_zones],
    ["streams", activity.has_streams],
  ];
  return (
    <div className="flex flex-wrap gap-1">
      {flags.map(([label, enabled]) => (
        <span
          key={String(label)}
          className={`px-1.5 py-0.5 rounded text-[11px] ${enabled ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-400"}`}
        >
          {label}
        </span>
      ))}
    </div>
  );
}

export function IngestionPage() {
  const [activities, setActivities] = useState<IngestedActivitiesResponse | null>(null);
  const [page, setPage] = useState(1);
  const [run, setRun] = useState<BackfillRun | null>(null);
  const [jobs, setJobs] = useState<BackfillJob[]>([]);
  const [pastRuns, setPastRuns] = useState<BackfillRun[]>([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [cleanupText, setCleanupText] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const loadActivities = useCallback(async () => {
    setActivities(await fetchIngestedActivities(page));
  }, [page]);

  const loadBackfillHistory = useCallback(async () => {
    setPastRuns(await fetchBackfillHistory());
  }, []);

  const loadRun = useCallback(async (id: number) => {
    const nextRun = await fetchBackfill(id);
    setRun(nextRun);
    setJobs(await fetchBackfillJobs(id));
    setPastRuns((runs) => {
      const withoutCurrent = runs.filter((item) => item.id !== nextRun.id);
      return [nextRun, ...withoutCurrent].slice(0, 10);
    });
    if (!activeStatuses.has(nextRun.status)) {
      await loadActivities();
    }
  }, [loadActivities]);

  useEffect(() => {
    loadActivities().catch(() => setMessage("Could not load ingested activities."));
  }, [loadActivities]);

  useEffect(() => {
    Promise.all([fetchLatestBackfill(), fetchBackfillHistory()])
      .then(([latestRun, history]) => {
        setPastRuns(history);
        if (latestRun) return loadRun(latestRun.id);
      })
      .catch(() => setMessage("Could not load latest backfill status."));
  }, [loadRun]);

  useEffect(() => {
    if (!run || !activeStatuses.has(run.status)) return;
    const timer = window.setInterval(() => {
      loadRun(run.id).catch(() => setMessage("Could not refresh backfill status."));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadRun, run]);

  const failedJobs = useMemo(() => jobs.filter((job) => job.status === "failed"), [jobs]);
  const rateLimitWaitMessage = run ? formatRateLimitWait(run) : null;

  const handleBackfill = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      const nextRun = await createBackfill({
        start_date: startDate,
        end_date: endDate,
        force_refresh: forceRefresh,
      });
      setRun(nextRun);
      setJobs([]);
      await loadRun(nextRun.id);
      await loadBackfillHistory();
    } catch {
      setMessage("Could not start backfill. Check the date range and Strava connection.");
    }
  };

  const handleRetry = async () => {
    if (!run) return;
    await retryFailedBackfill(run.id);
    await loadRun(run.id);
    await loadBackfillHistory();
  };

  const handleCancel = async () => {
    if (!run) return;
    await cancelBackfill(run.id);
    await loadRun(run.id);
    await loadBackfillHistory();
  };

  const handleCleanup = async () => {
    if (cleanupText !== "DELETE") return;
    await cleanupIngestedActivities();
    setCleanupText("");
    setRun(null);
    setJobs([]);
    setPastRuns([]);
    await loadActivities();
    setMessage("Ingestion tables cleaned up.");
  };

  return (
    <div className="space-y-6">
      {message && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-xl px-4 py-3 text-sm">
          {message}
        </div>
      )}

      <section className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Database Activities</h2>
            <p className="text-xs text-gray-500 mt-0.5">Activities stored in the new local analytics tables</p>
          </div>
          <button
            type="button"
            onClick={() => loadActivities()}
            className="text-sm px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100"
          >
            Refresh
          </button>
        </div>
        {!activities ? (
          <div className="px-5 py-4 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-4 bg-gray-200 rounded animate-pulse" />
            ))}
          </div>
        ) : activities.items.length === 0 ? (
          <p className="px-5 py-4 text-sm text-gray-500">No ingested activities yet. Run a backfill to populate the table.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Activity</th>
                    <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Date</th>
                    <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Sport</th>
                    <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Distance</th>
                    <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Time</th>
                    <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Data</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {activities.items.map((activity) => (
                    <tr key={activity.activity_id} className="hover:bg-gray-50 text-gray-600">
                      <td className="px-5 py-2">
                        <div className="font-medium text-gray-900">{activity.name ?? "Untitled activity"}</div>
                        <div className="text-gray-400">{activity.activity_id}</div>
                      </td>
                      <td className="px-5 py-2 whitespace-nowrap">{formatDate(activity.start_date_local)}</td>
                      <td className="px-5 py-2 whitespace-nowrap">{activity.sport_type ?? activity.activity_type ?? "-"}</td>
                      <td className="px-5 py-2 whitespace-nowrap">{formatDistance(activity.distance)}</td>
                      <td className="px-5 py-2 whitespace-nowrap">{formatDuration(activity.moving_time)}</td>
                      <td className="px-5 py-2"><DataFlags activity={activity} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-600">
              <span>Page {activities.page} of {Math.max(1, Math.ceil(activities.total / activities.per_page))}</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 rounded-md border border-gray-300 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page * activities.per_page >= activities.total}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 rounded-md border border-gray-300 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Run Backfill</h2>
            <p className="text-xs text-gray-500 mt-0.5">Discover Strava activities by date and ingest missing records</p>
          </div>
          <form onSubmit={handleBackfill} className="p-5 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="text-sm text-gray-700">
                Start date
                <input
                  type="date"
                  required
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                />
              </label>
              <label className="text-sm text-gray-700">
                End date
                <input
                  type="date"
                  required
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                />
              </label>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={forceRefresh}
                onChange={(event) => setForceRefresh(event.target.checked)}
                className="rounded border-gray-300"
              />
              Force refresh existing activities
            </label>
            <button
              type="submit"
              className="w-full px-4 py-2 rounded-md bg-orange-500 text-white font-medium hover:bg-orange-600"
            >
              Start backfill
            </button>
          </form>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Backfill Status</h2>
            <p className="text-xs text-gray-500 mt-0.5">Progress updates poll while a run is active</p>
          </div>
          {!run ? (
            <p className="px-5 py-4 text-sm text-gray-500">No backfill run selected.</p>
          ) : (
            <div className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900">Run #{run.id}</span>
                <StatusBadge status={run.status} />
              </div>
              <div className="grid grid-cols-3 gap-3 text-center text-sm">
                <div className="rounded-lg bg-gray-50 p-3"><div className="font-semibold">{run.queued_count}</div><div className="text-xs text-gray-500">Queued</div></div>
                <div className="rounded-lg bg-green-50 p-3"><div className="font-semibold">{run.succeeded_count}</div><div className="text-xs text-gray-500">Done</div></div>
                <div className="rounded-lg bg-red-50 p-3"><div className="font-semibold">{run.failed_count}</div><div className="text-xs text-gray-500">Failed</div></div>
              </div>
              {rateLimitWaitMessage && (
                <div className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-800">
                  {rateLimitWaitMessage}
                </div>
              )}
              {run.last_error && <p className="text-sm text-red-600">{run.last_error}</p>}
              <div className="flex gap-2">
                <button type="button" onClick={() => loadRun(run.id)} className="px-3 py-1.5 rounded-md border border-gray-300 text-sm">Refresh</button>
                {failedJobs.length > 0 && <button type="button" onClick={handleRetry} className="px-3 py-1.5 rounded-md border border-gray-300 text-sm">Retry failed</button>}
                {activeStatuses.has(run.status) && <button type="button" onClick={handleCancel} className="px-3 py-1.5 rounded-md border border-gray-300 text-sm">Cancel</button>}
              </div>
              {jobs.length > 0 && (
                <div className="max-h-48 overflow-auto border border-gray-100 rounded-lg">
                  <table className="min-w-full text-xs">
                    <tbody className="divide-y divide-gray-50">
                      {jobs.slice(0, 20).map((job) => (
                        <tr key={job.id}>
                          <td className="px-3 py-2">{job.activity_id}</td>
                          <td className="px-3 py-2"><StatusBadge status={job.status} /></td>
                          <td className="px-3 py-2 text-gray-500">{job.last_error ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Past Backfills</h2>
            <p className="text-xs text-gray-500 mt-0.5">Recent ingestion runs, including active rate-limited runs</p>
          </div>
          <button
            type="button"
            onClick={() => loadBackfillHistory().catch(() => setMessage("Could not refresh backfill history."))}
            className="text-sm px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100"
          >
            Refresh
          </button>
        </div>
        {pastRuns.length === 0 ? (
          <p className="px-5 py-4 text-sm text-gray-500">No backfills have been run yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Run</th>
                  <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Range</th>
                  <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Progress</th>
                  <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Updated</th>
                  <th className="px-5 py-2 text-left font-medium text-gray-500 uppercase tracking-wide">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {pastRuns.map((pastRun) => (
                  <tr key={pastRun.id} className="hover:bg-gray-50 text-gray-600">
                    <td className="px-5 py-2 whitespace-nowrap font-medium text-gray-900">#{pastRun.id}</td>
                    <td className="px-5 py-2 whitespace-nowrap">{formatDateOnly(pastRun.start_date)} to {formatDateOnly(pastRun.end_date)}</td>
                    <td className="px-5 py-2 whitespace-nowrap"><StatusBadge status={pastRun.status} /></td>
                    <td className="px-5 py-2 whitespace-nowrap">{backfillProgress(pastRun)}</td>
                    <td className="px-5 py-2 whitespace-nowrap">{formatDate(pastRun.updated_at)}</td>
                    <td className="px-5 py-2 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => loadRun(pastRun.id).catch(() => setMessage("Could not load selected backfill."))}
                        className="px-2.5 py-1 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="bg-white rounded-xl shadow-sm border border-red-200">
        <div className="px-5 py-4 border-b border-red-100">
          <h2 className="text-base font-semibold text-red-700">Development Cleanup</h2>
          <p className="text-xs text-gray-500 mt-0.5">Deletes only the new ingestion and backfill tables while developing</p>
        </div>
        <div className="p-5 flex flex-col sm:flex-row gap-3 sm:items-end">
          <label className="text-sm text-gray-700 flex-1">
            Type DELETE to confirm
            <input
              value={cleanupText}
              onChange={(event) => setCleanupText(event.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
              placeholder="DELETE"
            />
          </label>
          <button
            type="button"
            disabled={cleanupText !== "DELETE"}
            onClick={handleCleanup}
            className="px-4 py-2 rounded-md bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-40"
          >
            Delete ingestion records
          </button>
        </div>
      </section>
    </div>
  );
}

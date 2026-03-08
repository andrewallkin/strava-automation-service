import { useCallback, useEffect, useState } from "react";
import {
  GymSummary as GymSummaryType,
  Summary,
  fetchGymSummary,
  fetchSummary,
} from "../lib/api";
import { ShoeVault, StatsGrid, WeeklyTrainingSummary } from "./Dashboard";

function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function GymSummary() {
  const [data, setData] = useState<GymSummaryType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGymSummary()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-red-200 px-5 py-4">
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Gym Summary</h2>
        <p className="text-xs text-gray-500 mt-0.5">WeightTraining activity overview</p>
      </div>
      {data === null ? (
        <div className="px-5 py-4 space-y-3">
          <div className="h-4 bg-gray-200 rounded w-2/3 animate-pulse" />
          <div className="h-4 bg-gray-200 rounded w-1/2 animate-pulse" />
        </div>
      ) : (
        <div className="px-5 py-4 space-y-4">
          {/* This week / Last week */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded-lg px-4 py-3">
              <p className="text-xs text-gray-500 mb-1">This week</p>
              <p className="text-lg font-bold text-gray-900">{data.this_week.count}</p>
              <p className="text-xs text-gray-500">{formatDuration(data.this_week.duration_s)}</p>
            </div>
            <div className="bg-gray-50 rounded-lg px-4 py-3">
              <p className="text-xs text-gray-500 mb-1">Last week</p>
              <p className="text-lg font-bold text-gray-900">{data.last_week.count}</p>
              <p className="text-xs text-gray-500">{formatDuration(data.last_week.duration_s)}</p>
            </div>
          </div>

          {/* Year total */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">This year:</span>
            <span className="text-sm font-bold text-orange-500">{data.year_total} workouts</span>
          </div>

          {/* Monthly comparison */}
          {data.months.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2">Monthly</p>
              <div className="space-y-1.5">
                {data.months.map((m) => {
                  const maxCount = Math.max(...data.months.map((x) => x.count), 1);
                  const pct = (m.count / maxCount) * 100;
                  return (
                    <div key={m.month} className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-8">{m.month}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-3">
                        <div
                          className="bg-orange-400 h-3 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-600 w-20 text-right">
                        {m.count} · {formatDuration(m.duration_s)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function HomePage() {
  const [summary, setSummary] = useState<Summary | null>(null);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await fetchSummary());
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadSummary();
    const t = window.setInterval(loadSummary, 5000);
    return () => window.clearInterval(t);
  }, [loadSummary]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="space-y-4">
        <StatsGrid summary={summary} />
        <WeeklyTrainingSummary />
      </div>
      <div className="space-y-4">
        <ShoeVault />
        <GymSummary />
      </div>
    </div>
  );
}

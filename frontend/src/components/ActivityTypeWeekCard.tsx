import { useEffect, useState } from "react";
import { ActivityTypeSummary, SportTypeTotals, fetchActivityTypeSummary } from "../lib/api";
import { Trend, activityTypeRows, formatHoursMinutes, sportIcon, weekTotals } from "../lib/activityTypes";
import { ErrorCard } from "../pages/Dashboard";

const ROW_GRID = "grid grid-cols-[1fr_6rem_6rem_1.5rem] gap-x-2";

const TREND_DISPLAY: Record<Trend, { symbol: string; className: string }> = {
  up: { symbol: "↑", className: "text-green-500" },
  down: { symbol: "↓", className: "text-red-500" },
  flat: { symbol: "—", className: "text-gray-400" },
};

function WeekCell({ totals }: { totals: SportTypeTotals | null }) {
  if (!totals) return <span className="text-right text-gray-300">—</span>;
  return (
    <span className="text-right">
      <span className="font-semibold text-gray-900">{totals.activityCount}×</span>{" "}
      <span className="text-gray-600">{formatHoursMinutes(totals.movingTimeSec)}</span>
    </span>
  );
}

export function ActivityTypeWeekCard({ className }: { className?: string }) {
  const [data, setData] = useState<ActivityTypeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchActivityTypeSummary()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load activity types"));
  }, []);

  if (error) return <ErrorCard message={error} />;

  const rows = data ? activityTypeRows(data) : [];
  const totals = data ? weekTotals(data.thisWeek) : null;

  return (
    <div className={`flex flex-col bg-white rounded-xl shadow-sm border border-gray-200${className ? ` ${className}` : ""}`}>
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">This Week by Activity Type</h2>
        <p className="text-xs text-gray-500 mt-0.5">Grouped by Strava sport_type · this week vs last week</p>
      </div>
      {data === null ? (
        <div className="px-5 py-4 space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-6 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No activities this week or last week.</p>
      ) : (
        <div className="px-5 py-4 flex-1 flex flex-col">
          <div className={`${ROW_GRID} px-1 pb-1 text-[10px] font-medium text-gray-400 uppercase tracking-wide`}>
            <span>sport_type</span>
            <span className="text-right">This week</span>
            <span className="text-right">Last week</span>
            <span />
          </div>
          <div className="space-y-1">
            {rows.map((row) => (
              <div key={row.sportType} className={`${ROW_GRID} items-center px-1 py-1.5 rounded-lg bg-gray-50 text-xs`}>
                <span className="flex items-center gap-2 min-w-0">
                  <span aria-hidden="true">{sportIcon(row.sportType)}</span>
                  <span className="font-medium text-gray-900 truncate">{row.sportType}</span>
                </span>
                <WeekCell totals={row.thisWeek} />
                <WeekCell totals={row.lastWeek} />
                <span className={`text-right ${TREND_DISPLAY[row.trend].className}`}>{TREND_DISPLAY[row.trend].symbol}</span>
              </div>
            ))}
          </div>
          {totals && (
            <div className="mt-auto pt-3 border-t border-gray-100 flex justify-between text-xs">
              <span className="text-gray-500">Total this week</span>
              <span className="font-semibold text-gray-900">
                {totals.activityCount} {totals.activityCount === 1 ? "activity" : "activities"} · {formatHoursMinutes(totals.movingTimeSec)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

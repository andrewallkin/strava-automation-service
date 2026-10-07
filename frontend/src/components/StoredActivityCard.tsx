import type { StoredActivity } from "../lib/api";
import { activityCardFacts, isRunSport, sportIcon } from "../lib/activityTypes";
import { formatStravaLocalDateTime } from "../lib/datetimeDisplay";

export function StoredActivityCard({ activity, compact = false }: { activity: StoredActivity; compact?: boolean }) {
  const sportType = activity.sportType ?? "Unknown";
  const accent = isRunSport(activity.sportType) ? "border-l-orange-400" : "border-l-gray-300";

  return (
    <div className={`flex gap-4 px-5 ${compact ? "py-3" : "py-4"} hover:bg-gray-50 transition-colors border-l-4 ${accent}`}>
      <div className="text-2xl leading-none mt-0.5" aria-hidden="true">
        {sportIcon(activity.sportType)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-gray-900 truncate">{activity.name ?? sportType}</p>
          <p className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">
            {formatStravaLocalDateTime(activity.startDateLocal)}
          </p>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-500">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700">
            {sportType}
          </span>
          {activityCardFacts(activity, compact).map((fact) => (
            <span key={fact.key}>{fact.text}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

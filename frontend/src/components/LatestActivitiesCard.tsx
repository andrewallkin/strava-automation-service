import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StoredActivity, fetchStoredActivities } from "../lib/api";
import { ErrorCard } from "../pages/Dashboard";
import { StoredActivityCard } from "./StoredActivityCard";

const LATEST_COUNT = 5;

export function LatestActivitiesCard({ className }: { className?: string }) {
  const [activities, setActivities] = useState<StoredActivity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStoredActivities(1, LATEST_COUNT)
      .then((page) => setActivities(page.data))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load activities"));
  }, []);

  if (error) return <ErrorCard message={error} />;

  return (
    <div className={`flex flex-col bg-white rounded-xl shadow-sm border border-gray-200${className ? ` ${className}` : ""}`}>
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Latest Activities</h2>
          <p className="text-xs text-gray-500 mt-0.5">All types, newest first</p>
        </div>
        <Link to="/activities" className="text-xs font-medium text-orange-600 hover:text-orange-700 whitespace-nowrap">
          View all →
        </Link>
      </div>
      {activities === null ? (
        <div className="px-5 py-4 space-y-3">
          {[...Array(LATEST_COUNT)].map((_, i) => (
            <div key={i} className="h-8 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      ) : activities.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No activities yet.</p>
      ) : (
        <div className="flex-1 divide-y divide-gray-100">
          {activities.map((activity) => (
            <StoredActivityCard key={activity.id} activity={activity} compact />
          ))}
        </div>
      )}
    </div>
  );
}

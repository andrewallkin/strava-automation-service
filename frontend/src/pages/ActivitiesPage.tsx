import { useEffect, useState } from "react";
import { StoredActivityCard } from "../components/StoredActivityCard";
import { StoredActivity, fetchStoredActivities } from "../lib/api";
import { ErrorCard } from "./Dashboard";

const PAGE_SIZE = 15;

export function ActivitiesPage() {
  const [activities, setActivities] = useState<StoredActivity[] | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    fetchStoredActivities(1, PAGE_SIZE)
      .then((page) => {
        setActivities(page.data);
        setNextPage(page.pagination.nextPage);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load activities"));
  }, []);

  async function loadMore() {
    if (nextPage === null || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await fetchStoredActivities(nextPage, PAGE_SIZE);
      setActivities((current) => [...(current ?? []), ...page.data]);
      setNextPage(page.pagination.nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load more activities");
    } finally {
      setLoadingMore(false);
    }
  }

  if (error) return <ErrorCard message={error} />;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Activities</h2>
        <p className="text-xs text-gray-500 mt-0.5">Every ingested activity, labelled with its Strava sport_type</p>
      </div>
      {activities === null ? (
        <div className="px-5 py-4 space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      ) : activities.length === 0 ? (
        <p className="px-5 py-4 text-sm text-gray-500">No activities yet.</p>
      ) : (
        <>
          <div className="divide-y divide-gray-100">
            {activities.map((activity) => (
              <StoredActivityCard key={activity.id} activity={activity} />
            ))}
          </div>
          {nextPage !== null && (
            <div className="px-5 py-3 border-t border-gray-100 text-center">
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="text-sm font-medium text-orange-600 hover:text-orange-700 disabled:opacity-50"
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

import { useCallback, useState } from "react";
import { ActivityTypeWeekCard } from "../components/ActivityTypeWeekCard";
import { LatestActivitiesCard } from "../components/LatestActivitiesCard";
import { Summary, fetchSummary } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { ShoeVault, StatsGrid } from "./Dashboard";

export function HomePage() {
  const [summary, setSummary] = useState<Summary | null>(null);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await fetchSummary());
    } catch {
      // ignore
    }
  }, []);

  usePolling(loadSummary, 5000);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <ActivityTypeWeekCard className="h-full" />
      <LatestActivitiesCard className="h-full" />
      <StatsGrid summary={summary} className="h-full" />
      <ShoeVault className="h-full" />
    </div>
  );
}

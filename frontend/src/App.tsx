import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Status, fetchStatus } from "./lib/api";
import { ActivitiesPage } from "./pages/ActivitiesPage";
import { EventsPage } from "./pages/EventsPage";
import { HomePage } from "./pages/HomePage";
import { IngestionPage } from "./pages/IngestionPage";
import { Login } from "./pages/Login";
import { SettingsPage } from "./pages/SettingsPage";
import { StravaExplorerPage } from "./pages/StravaExplorerPage";
import { VectorStorePage } from "./pages/VectorStorePage";

export default function App() {
  const [status, setStatus] = useState<Status | null | "loading">("loading");

  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchStatus();
      setStatus(s ?? null);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Handle ?strava=connected message
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-4 border-orange-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!status?.connected) {
    return <Login />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout status={status} onLogout={() => setStatus(null)} />}>
          <Route index element={<HomePage />} />
          <Route path="activities" element={<ActivitiesPage />} />
          <Route path="ingestion" element={<IngestionPage />} />
          <Route path="strava-explorer" element={<StravaExplorerPage />} />
          <Route path="vector-store" element={<VectorStorePage />} />
          <Route path="events" element={<EventsPage />} />
          <Route
            path="settings"
            element={<SettingsPage status={status} onStatusChange={setStatus} />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

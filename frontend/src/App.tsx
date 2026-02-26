import { useCallback, useEffect, useState } from "react";
import { Status, fetchStatus } from "./lib/api";
import { Login } from "./pages/Login";
import { Settings } from "./pages/Settings";

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

  return <Settings status={status} onStatusChange={setStatus} />;
}

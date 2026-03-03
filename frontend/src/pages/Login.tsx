import { useState } from "react";
import { login } from "../lib/api";

export function Login() {
  const [loading, setLoading] = useState(false);
  const params = new URLSearchParams(window.location.search);
  const error = params.get("strava") === "error"
    ? (params.get("message") ?? "Authentication failed. Please try again.")
    : null;

  async function handleSignIn() {
    setLoading(true);
    try {
      const ok = await login();
      if (ok) {
        window.location.href = "/";
        return;
      }
      window.location.href = "/api/auth/strava/connect";
    } catch {
      window.location.href = "/api/auth/strava/connect";
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-gray-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8 text-center space-y-6">
          {/* Logo + branding */}
          <div className="flex flex-col items-center gap-3">
            <img src="/logo.png" alt="Strava Automation" className="h-16 w-16 object-contain" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Strava <span className="text-orange-500">Automation</span>
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                Auto-log shoes and hide gym workouts
              </p>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div
              role="alert"
              className="rounded-lg px-4 py-3 text-sm bg-red-50 text-red-700 border border-red-200 text-left"
            >
              {error}
            </div>
          )}

          {/* Connect button */}
          <button
            type="button"
            onClick={handleSignIn}
            disabled={loading}
            className="flex items-center justify-center gap-2 w-full px-6 py-3 bg-orange-500 hover:bg-orange-600 active:bg-orange-700 disabled:opacity-70 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors shadow-sm"
          >
            {loading && (
              <span className="h-5 w-5 rounded-full border-2 border-white border-t-transparent animate-spin" />
            )}
            Continue with Strava
          </button>
        </div>
      </div>
    </div>
  );
}

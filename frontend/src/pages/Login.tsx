export function Login() {
  const params = new URLSearchParams(window.location.search);
  const error = params.get("strava") === "error"
    ? (params.get("message") ?? "Authentication failed. Please try again.")
    : null;

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
          <a
            href="/api/auth/strava/connect"
            className="flex items-center justify-center gap-2 w-full px-6 py-3 bg-orange-500 hover:bg-orange-600 active:bg-orange-700 text-white font-semibold rounded-lg transition-colors shadow-sm"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
              <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066l-2.084 4.116z" />
              <path d="M11.233 13.828L9.145 9.705H6.08L11.233 19.88l5.153-10.175h-3.066l-2.087 4.123z" />
            </svg>
            Continue with Strava
          </a>
        </div>
      </div>
    </div>
  );
}

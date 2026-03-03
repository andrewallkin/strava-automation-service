const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const FETCH_OPTS: RequestInit = { credentials: "include" };

function handle401(response: Response, redirectOn401: boolean): void {
  if (response.status === 401) {
    if (redirectOn401) {
      window.location.href = "/";
    }
    throw new Error("Unauthorized");
  }
}

export type Summary = {
  pending_count: number;
  last_event_at: string | null;
  last_event_message: string | null;
  runs_updated: number;
  gym_hidden: number;
};

export type PendingActivity = {
  activity_id: number;
  telegram_message_id: number;
  created_at: string;
};

export type Status = {
  connected: boolean;
  strava_athlete_id?: number;
  athlete_name: string | null;
  athlete_profile_url: string | null;
  run_shoe_enabled: boolean;
  gym_hide_enabled: boolean;
};

export type StravaActivity = {
  id: number;
  name: string | null;
  type: string | null;
  sport_type: string | null;
  distance: number | null;
  moving_time: number | null;
  total_elevation_gain: number | null;
  average_heartrate: number | null;
  start_date_local: string | null;
};

export type SettingsUpdate = {
  run_shoe_enabled?: boolean;
  gym_hide_enabled?: boolean;
};

export type EventRow = {
  id: number;
  event_type: string;
  status: string;
  message: string;
  payload: unknown;
  correlation_id: string | null;
  created_at: string;
};

async function getJson<T>(path: string, redirectOn401 = true): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, FETCH_OPTS);
  handle401(response, redirectOn401);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchStatus(): Promise<Status | null> {
  const response = await fetch(`${API_BASE}/ui/status`, FETCH_OPTS);
  if (response.status === 401) return null;
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return (await response.json()) as Status;
}

export async function updateSettings(settings: SettingsUpdate): Promise<Status> {
  const response = await fetch(`${API_BASE}/ui/settings`, {
    ...FETCH_OPTS,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings)
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return (await response.json()) as Status;
}

export async function fetchSummary(): Promise<Summary> {
  return getJson<Summary>("/ui/summary");
}

export async function fetchPending(): Promise<PendingActivity[]> {
  return getJson<PendingActivity[]>("/ui/pending");
}

export async function fetchEvents(): Promise<EventRow[]> {
  return getJson<EventRow[]>("/ui/events");
}

export async function retryActivity(activityId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/ui/retry/${activityId}`, {
    ...FETCH_OPTS,
    method: "POST"
  });
  handle401(response, true);
  if (!response.ok) {
    throw new Error(`Retry failed: ${response.status}`);
  }
}

export async function fetchActivities(page = 1): Promise<StravaActivity[]> {
  const params = new URLSearchParams({ page: String(page), per_page: "15" });
  return getJson<StravaActivity[]>(`/ui/activities?${params}`);
}

export async function logout(): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/logout`, {
    ...FETCH_OPTS,
    method: "POST"
  });
  handle401(response, true);
  if (!response.ok) {
    throw new Error(`Logout failed: ${response.status}`);
  }
}

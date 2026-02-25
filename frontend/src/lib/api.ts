const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

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
  run_shoe_enabled: boolean;
  gym_hide_enabled: boolean;
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

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchStatus(): Promise<Status | null> {
  const response = await fetch(`${API_BASE}/ui/status`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return (await response.json()) as Status;
}

export async function updateSettings(settings: SettingsUpdate): Promise<Status> {
  const response = await fetch(`${API_BASE}/ui/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings)
  });
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
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`Retry failed: ${response.status}`);
  }
}

export async function disconnectStrava(): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/strava/disconnect`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(`Disconnect failed: ${response.status}`);
  }
}

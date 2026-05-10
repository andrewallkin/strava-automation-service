const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const FETCH_OPTS: RequestInit = { credentials: "include" };

/** Dynamic UI data must not use the HTTP cache (GET after DELETE can otherwise look stale). */
const NO_STORE_FETCH: RequestInit = { ...FETCH_OPTS, cache: "no-store" };

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

export type IngestedActivity = {
  activity_id: number;
  name: string | null;
  description: string | null;
  activity_type: string | null;
  sport_type: string | null;
  start_date: string | null;
  start_date_local: string | null;
  distance: number | null;
  moving_time: number | null;
  elapsed_time: number | null;
  total_elevation_gain: number | null;
  average_heartrate: number | null;
  average_watts: number | null;
  weighted_average_watts: number | null;
  gear_id: string | null;
  trainer: boolean | null;
  commute: boolean | null;
  has_laps: boolean;
  has_splits: boolean;
  has_segments: boolean;
  has_best_efforts: boolean;
  has_zones: boolean;
  has_streams: boolean;
  last_ingested_at: string | null;
  deleted_at: string | null;
};

export type IngestedActivitiesResponse = {
  items: IngestedActivity[];
  page: number;
  per_page: number;
  total: number;
};

export type BackfillRun = {
  id: number;
  athlete_id: number;
  start_date: string;
  end_date: string;
  force_refresh: boolean;
  status: string;
  requested_count: number;
  missing_count: number;
  queued_count: number;
  succeeded_count: number;
  failed_count: number;
  skipped_count: number;
  last_error: string | null;
  rate_limit_wait_until: string | null;
  rate_limit_wait_reason: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
};

export type BackfillJob = {
  id: number;
  activity_id: number;
  athlete_id: number | null;
  trigger_type: string;
  aspect_type: string | null;
  status: string;
  attempt_count: number;
  last_error: string | null;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
};

export type SettingsUpdate = {
  run_shoe_enabled?: boolean;
  gym_hide_enabled?: boolean;
};

export type McpApiKey = {
  id: number;
  name: string | null;
  key_prefix: string;
  created_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  api_key?: string;
};

export type OpenAiApiKeyStatus = {
  configured: boolean;
  key_prefix: string | null;
  updated_at: string | null;
};

export type CoachSettings = {
  vector_store_id: string | null;
  agent_name: string;
  agent_instructions: string;
  openai_model: string;
  telegram_user_id: number | null;
  telegram_linked: boolean;
};

export type CoachSettingsUpdate = {
  vector_store_id?: string | null;
  agent_name?: string;
  agent_instructions?: string;
  openai_model?: string;
};

export type CoachLinkCodeResponse = {
  code: string;
  expires_in_seconds: number;
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

export type StravaExplorerMethod = "GET" | "POST" | "PUT" | "DELETE";

export type StravaExplorerRequest = {
  method: StravaExplorerMethod;
  endpoint: string;
  params?: Record<string, unknown>;
  body?: unknown;
  body_encoding?: "json" | "form";
};

export type StravaExplorerResponse = {
  method: StravaExplorerMethod;
  endpoint: string;
  url: string;
  status_code: number;
  headers: Record<string, string>;
  body: unknown;
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

export async function fetchMcpApiKeys(): Promise<McpApiKey[]> {
  return getJson<McpApiKey[]>("/ui/mcp-api-keys");
}

export async function createMcpApiKey(name?: string): Promise<McpApiKey> {
  const response = await fetch(`${API_BASE}/ui/mcp-api-keys`, {
    ...FETCH_OPTS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name || null })
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Key generation failed: ${response.status}`);
  return (await response.json()) as McpApiKey;
}

export async function revokeMcpApiKey(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/ui/mcp-api-keys/${id}`, {
    ...FETCH_OPTS,
    method: "DELETE"
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Revoke failed: ${response.status}`);
}

export async function fetchOpenAiApiKeyStatus(): Promise<OpenAiApiKeyStatus> {
  return getJson<OpenAiApiKeyStatus>("/ui/openai-api-key");
}

async function parseFastApiError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      const first = body.detail[0] as { msg?: string } | undefined;
      if (first && typeof first.msg === "string") return first.msg;
    }
  } catch {
    /* ignore */
  }
  return `Request failed: ${response.status}`;
}

export async function saveOpenAiApiKey(apiKey: string): Promise<OpenAiApiKeyStatus> {
  const response = await fetch(`${API_BASE}/ui/openai-api-key`, {
    ...FETCH_OPTS,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey })
  });
  handle401(response, true);
  if (!response.ok) throw new Error(await parseFastApiError(response));
  return (await response.json()) as OpenAiApiKeyStatus;
}

export async function deleteOpenAiApiKey(): Promise<void> {
  const response = await fetch(`${API_BASE}/ui/openai-api-key`, {
    ...FETCH_OPTS,
    method: "DELETE"
  });
  handle401(response, true);
  if (!response.ok) throw new Error(await parseFastApiError(response));
}

export async function fetchCoachSettings(): Promise<CoachSettings> {
  return getJson<CoachSettings>("/ui/coach/settings");
}

export async function updateCoachSettings(input: CoachSettingsUpdate): Promise<CoachSettings> {
  const response = await fetch(`${API_BASE}/ui/coach/settings`, {
    ...FETCH_OPTS,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
  handle401(response, true);
  if (!response.ok) throw new Error(await parseFastApiError(response));
  return (await response.json()) as CoachSettings;
}

export async function createCoachLinkCode(): Promise<CoachLinkCodeResponse> {
  const response = await fetch(`${API_BASE}/ui/coach/link-code`, {
    ...FETCH_OPTS,
    method: "POST"
  });
  handle401(response, true);
  if (!response.ok) throw new Error(await parseFastApiError(response));
  return (await response.json()) as CoachLinkCodeResponse;
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

export async function callStravaExplorer(
  request: StravaExplorerRequest
): Promise<StravaExplorerResponse> {
  const response = await fetch(`${API_BASE}/ui/strava-explorer`, {
    ...FETCH_OPTS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  handle401(response, true);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return (await response.json()) as StravaExplorerResponse;
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

export async function fetchIngestedActivities(page = 1): Promise<IngestedActivitiesResponse> {
  const params = new URLSearchParams({ page: String(page), per_page: "25" });
  return getJson<IngestedActivitiesResponse>(`/ui/ingested-activities?${params}`);
}

export async function createBackfill(input: {
  start_date: string;
  end_date: string;
  force_refresh: boolean;
}): Promise<BackfillRun> {
  const response = await fetch(`${API_BASE}/ui/backfill`, {
    ...FETCH_OPTS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Backfill failed: ${response.status}`);
  return (await response.json()) as BackfillRun;
}

export async function fetchBackfill(id: number): Promise<BackfillRun> {
  return getJson<BackfillRun>(`/ui/backfill/${id}`);
}

export async function fetchLatestBackfill(): Promise<BackfillRun | null> {
  return getJson<BackfillRun | null>("/ui/backfill/latest");
}

export async function fetchBackfillHistory(limit = 10): Promise<BackfillRun[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return getJson<BackfillRun[]>(`/ui/backfill/history?${params}`);
}

export async function fetchBackfillJobs(id: number): Promise<BackfillJob[]> {
  return getJson<BackfillJob[]>(`/ui/backfill/${id}/jobs`);
}

export async function retryFailedBackfill(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/ui/backfill/${id}/retry-failed`, {
    ...FETCH_OPTS,
    method: "POST"
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Retry failed: ${response.status}`);
}

export async function cancelBackfill(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/ui/backfill/${id}/cancel`, {
    ...FETCH_OPTS,
    method: "POST"
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Cancel failed: ${response.status}`);
}

export async function cleanupIngestedActivities(): Promise<void> {
  const response = await fetch(`${API_BASE}/ui/ingested-activities/dev-cleanup`, {
    ...FETCH_OPTS,
    method: "DELETE"
  });
  handle401(response, true);
  if (!response.ok) throw new Error(`Cleanup failed: ${response.status}`);
}

export type ShoeVaultEntry = {
  strava_gear_id: string;
  name: string;
  is_default: boolean;
  total_distance_m: number;
  brand_name: string | null;
  model_name: string | null;
};

export type DayActivity = {
  name: string;
  km: number;
  moving_time_s: number;
  elevation_m: number;
};

export type DayStats = {
  km: number;
  moving_time_s: number;
  elevation_m: number;
  count: number;
  activities: DayActivity[];
};

export type WeekStats = {
  total_km: number;
  run_count: number;
  elevation_m: number;
  days: DayStats[];
};

export type WeeklySummary = {
  this_week: WeekStats;
  last_week: WeekStats;
};

export type PrEntry = {
  activity_name: string | null;
  activity_date: string;
  distance_m: number;
  moving_time_s: number;
  value_sec_per_km?: number;
  elevation_m?: number;
} | null;

export type StreakData = {
  current_streak: number;
  best_streak: number;
  prs: {
    fastest_pace: PrEntry;
    longest_run: PrEntry;
    most_elevation: PrEntry;
  };
};

export type GymCalendar = {
  gym_days: string[];
  month_session_count: number;
  weeks_with_gym_streak: number;
  year: number;
  month: number;
};

export async function fetchShoeVault(): Promise<ShoeVaultEntry[]> {
  return getJson<ShoeVaultEntry[]>("/ui/shoe-vault");
}

export async function fetchWeeklySummary(): Promise<WeeklySummary> {
  return getJson<WeeklySummary>("/ui/weekly-summary");
}

export async function fetchStreak(): Promise<StreakData> {
  return getJson<StreakData>("/ui/streak");
}

export async function fetchGymCalendar(): Promise<GymCalendar> {
  return getJson<GymCalendar>("/ui/gym-calendar");
}

export type GymMonthEntry = {
  month: string;
  count: number;
  duration_s: number;
};

export type GymSummary = {
  this_week: { count: number; duration_s: number };
  last_week: { count: number; duration_s: number };
  year_total: number;
  months: GymMonthEntry[];
};

export async function fetchGymSummary(): Promise<GymSummary> {
  return getJson<GymSummary>("/ui/gym-summary");
}

/** Max upload size for vector store files (must match backend). */
export const VECTOR_STORE_MAX_FILE_BYTES = 10 * 1024 * 1024;

export type VectorStore = {
  id: string;
  name: string | null;
  status: string | null;
  created_at: number | null;
  file_counts: Record<string, number> | null;
};

export type VectorStoreFileRow = {
  file_id: string;
  vector_store_id: string;
  status: string | null;
  created_at: number | null;
  usage_bytes: number | null;
  filename: string | null;
};

export type VectorStoreListResponse = {
  data: VectorStore[];
  has_more: boolean;
  last_id: string | null;
};

export type VectorStoreFilesResponse = {
  data: VectorStoreFileRow[];
  has_more: boolean;
  last_id: string | null;
};

async function readUiErrorMessage(response: Response): Promise<string> {
  const base = `Request failed: ${response.status}`;
  try {
    const j = (await response.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const parts = d.map((x) =>
        typeof x === "object" && x && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)
      );
      return parts.join(", ") || base;
    }
  } catch {
    /* ignore */
  }
  return base;
}

export async function fetchVectorStores(params?: {
  limit?: number;
  after?: string | null;
}): Promise<VectorStoreListResponse> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.after) sp.set("after", params.after);
  const q = sp.toString();
  const response = await fetch(`${API_BASE}/ui/vector-stores${q ? `?${q}` : ""}`, NO_STORE_FETCH);
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
  return (await response.json()) as VectorStoreListResponse;
}

export async function createVectorStore(name?: string | null): Promise<VectorStore> {
  const response = await fetch(`${API_BASE}/ui/vector-stores`, {
    ...FETCH_OPTS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name?.trim() || null })
  });
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
  return (await response.json()) as VectorStore;
}

export async function fetchVectorStore(vectorStoreId: string): Promise<VectorStore> {
  const response = await fetch(
    `${API_BASE}/ui/vector-stores/${encodeURIComponent(vectorStoreId)}`,
    NO_STORE_FETCH
  );
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
  return (await response.json()) as VectorStore;
}

export async function deleteVectorStore(vectorStoreId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE}/ui/vector-stores/${encodeURIComponent(vectorStoreId)}`,
    {
      ...FETCH_OPTS,
      method: "DELETE"
    }
  );
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
}

export async function fetchVectorStoreFiles(
  vectorStoreId: string,
  params?: { limit?: number; after?: string | null }
): Promise<VectorStoreFilesResponse> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.after) sp.set("after", params.after);
  const q = sp.toString();
  const response = await fetch(
    `${API_BASE}/ui/vector-stores/${encodeURIComponent(vectorStoreId)}/files${q ? `?${q}` : ""}`,
    NO_STORE_FETCH
  );
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
  return (await response.json()) as VectorStoreFilesResponse;
}

export async function uploadVectorStoreFile(
  vectorStoreId: string,
  file: File
): Promise<VectorStoreFileRow> {
  const fd = new FormData();
  fd.append("file", file);
  const response = await fetch(
    `${API_BASE}/ui/vector-stores/${encodeURIComponent(vectorStoreId)}/files`,
    {
      ...FETCH_OPTS,
      method: "POST",
      body: fd
    }
  );
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
  return (await response.json()) as VectorStoreFileRow;
}

export async function deleteVectorStoreFile(
  vectorStoreId: string,
  fileId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/ui/vector-stores/${encodeURIComponent(vectorStoreId)}/files/${encodeURIComponent(fileId)}`,
    {
      ...FETCH_OPTS,
      method: "DELETE"
    }
  );
  handle401(response, true);
  if (!response.ok) throw new Error(await readUiErrorMessage(response));
}

export async function disconnectStrava(): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/strava/disconnect`, {
    ...FETCH_OPTS,
    method: "DELETE"
  });
  handle401(response, true);
  if (!response.ok) {
    throw new Error(`Disconnect failed: ${response.status}`);
  }
}

export async function login(): Promise<boolean> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    ...FETCH_OPTS,
    method: "POST"
  });
  if (response.ok) return true;
  if (response.status === 401 || response.status === 404) return false;
  throw new Error(`Login failed: ${response.status}`);
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

import { FormEvent, useState } from "react";
import {
  StravaExplorerMethod,
  StravaExplorerResponse,
  callStravaExplorer,
} from "../lib/api";

type ExampleRequest = {
  label: string;
  method: StravaExplorerMethod;
  endpoint: string;
  params?: string;
  body?: string;
};

const examples: ExampleRequest[] = [
  {
    label: "Current athlete",
    method: "GET",
    endpoint: "/athlete",
  },
  {
    label: "Recent activities",
    method: "GET",
    endpoint: "/athlete/activities?per_page=5&page=1",
  },
  {
    label: "Activity detail",
    method: "GET",
    endpoint: "/activities/{activity_id}",
  },
  {
    label: "Activity streams",
    method: "GET",
    endpoint: "/activities/{activity_id}/streams",
    params: JSON.stringify(
      {
        keys: "time,distance,heartrate",
        key_by_type: true,
      },
      null,
      2
    ),
  },
];

const methods: StravaExplorerMethod[] = ["GET", "POST", "PUT", "DELETE"];

function parseJsonInput(value: string, label: string, requireObject = false): unknown {
  const trimmed = value.trim();
  if (!trimmed) return undefined;

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (
      requireObject &&
      (parsed === null || Array.isArray(parsed) || typeof parsed !== "object")
    ) {
      throw new Error(`${label} must be a JSON object.`);
    }
    return parsed;
  } catch (err) {
    if (err instanceof SyntaxError) {
      throw new Error(`${label} is not valid JSON.`);
    }
    throw err;
  }
}

function statusClasses(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) return "bg-green-100 text-green-700";
  if (statusCode >= 400) return "bg-red-100 text-red-700";
  return "bg-yellow-100 text-yellow-700";
}

function prettyJson(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2) ?? "";
}

export function StravaExplorerPage() {
  const [method, setMethod] = useState<StravaExplorerMethod>("GET");
  const [endpoint, setEndpoint] = useState("/athlete");
  const [params, setParams] = useState("");
  const [body, setBody] = useState("");
  const [bodyEncoding, setBodyEncoding] = useState<"json" | "form">("json");
  const [response, setResponse] = useState<StravaExplorerResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const applyExample = (example: ExampleRequest) => {
    setMethod(example.method);
    setEndpoint(example.endpoint);
    setParams(example.params ?? "");
    setBody(example.body ?? "");
    setMessage(null);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    setResponse(null);

    let parsedParams: Record<string, unknown> | undefined;
    let parsedBody: unknown;
    try {
      parsedParams = parseJsonInput(params, "Query params", true) as
        | Record<string, unknown>
        | undefined;
      parsedBody = parseJsonInput(body, "Request body", bodyEncoding === "form");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not parse request JSON.");
      return;
    }

    setLoading(true);
    try {
      setResponse(
        await callStravaExplorer({
          method,
          endpoint: endpoint.trim(),
          params: parsedParams,
          body: parsedBody,
          body_encoding: bodyEncoding,
        })
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {message && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
          {message}
        </div>
      )}

      <section className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Strava API Explorer</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Test Strava reference endpoints through the backend using your connected account.
            </p>
          </div>
          <a
            href="https://developers.strava.com/docs/reference/"
            target="_blank"
            rel="noreferrer"
            className="text-sm text-orange-600 hover:text-orange-700 font-medium"
          >
            Open Strava docs
          </a>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          <div className="flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example.label}
                type="button"
                onClick={() => applyExample(example)}
                className="px-3 py-1.5 rounded-md border border-gray-300 text-sm text-gray-700 hover:bg-gray-100"
              >
                {example.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[140px_1fr] gap-3">
            <label className="text-sm text-gray-700">
              Method
              <select
                value={method}
                onChange={(event) => setMethod(event.target.value as StravaExplorerMethod)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 bg-white"
              >
                {methods.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm text-gray-700">
              Endpoint
              <input
                value={endpoint}
                onChange={(event) => setEndpoint(event.target.value)}
                placeholder="/athlete/activities?per_page=5&page=1"
                required
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm"
              />
            </label>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <label className="text-sm text-gray-700">
              Query params JSON
              <textarea
                value={params}
                onChange={(event) => setParams(event.target.value)}
                rows={7}
                placeholder={'{\n  "per_page": 5,\n  "page": 1\n}'}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-xs"
              />
              <span className="mt-1 block text-xs text-gray-500">
                Optional. You can also put query params directly in the endpoint.
              </span>
            </label>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <label className="text-sm text-gray-700 flex-1">
                  Request body
                  <textarea
                    value={body}
                    onChange={(event) => setBody(event.target.value)}
                    rows={7}
                    placeholder={'{\n  "name": "Updated activity name"\n}'}
                    className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-xs"
                  />
                </label>
              </div>
              <label className="text-sm text-gray-700 block">
                Body encoding
                <select
                  value={bodyEncoding}
                  onChange={(event) => setBodyEncoding(event.target.value as "json" | "form")}
                  className="mt-1 rounded-md border border-gray-300 px-3 py-2 bg-white"
                >
                  <option value="json">JSON</option>
                  <option value="form">Form</option>
                </select>
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded-md bg-orange-500 text-white font-medium hover:bg-orange-600 disabled:opacity-50"
          >
            {loading ? "Calling Strava..." : "Send request"}
          </button>
        </form>
      </section>

      <section className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Response</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Raw response metadata and body from Strava.
          </p>
        </div>

        {!response ? (
          <p className="px-5 py-4 text-sm text-gray-500">Send a request to see the JSON response.</p>
        ) : (
          <div className="p-5 space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded font-medium ${statusClasses(
                  response.status_code
                )}`}
              >
                {response.status_code}
              </span>
              <span className="font-mono text-gray-700">{response.method}</span>
              <span className="font-mono text-gray-500 break-all">{response.url}</span>
            </div>

            {Object.keys(response.headers).length > 0 && (
              <div className="rounded-lg border border-gray-200 overflow-hidden">
                {Object.entries(response.headers).map(([key, value]) => (
                  <div
                    key={key}
                    className="grid grid-cols-1 sm:grid-cols-[220px_1fr] gap-1 px-3 py-2 text-xs border-b border-gray-100 last:border-b-0"
                  >
                    <span className="font-mono text-gray-500">{key}</span>
                    <span className="font-mono text-gray-800 break-all">{value}</span>
                  </div>
                ))}
              </div>
            )}

            <pre className="max-h-[36rem] overflow-auto rounded-lg bg-gray-950 text-gray-100 p-4 text-xs leading-relaxed">
              {prettyJson(response.body)}
            </pre>
          </div>
        )}
      </section>
    </div>
  );
}

import { useEffect, useState } from "react";
import {
  McpApiKey,
  Status,
  createMcpApiKey,
  disconnectStrava,
  fetchMcpApiKeys,
  revokeMcpApiKey,
  updateSettings
} from "../lib/api";

function Toggle({
  checked,
  onChange,
  id,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  id: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      id={id}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 ${
        checked ? "bg-orange-500" : "bg-gray-200"
      }`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

type SettingsPageProps = {
  status: Status;
  onStatusChange: (s: Status | null) => void;
};

export function SettingsPage({ status, onStatusChange }: SettingsPageProps) {
  const [localStatus, setLocalStatus] = useState<Status>(status);
  const [message, setMessage] = useState<string | null>(null);
  const [mcpKeys, setMcpKeys] = useState<McpApiKey[]>([]);
  const [newMcpKey, setNewMcpKey] = useState<string | null>(null);
  const [mcpKeyName, setMcpKeyName] = useState("Claude Desktop");

  useEffect(() => {
    fetchMcpApiKeys()
      .then(setMcpKeys)
      .catch((err) => setMessage(err instanceof Error ? err.message : "Failed to load MCP keys"));
  }, []);

  const handleToggle = async (key: "run_shoe_enabled" | "gym_hide_enabled", value: boolean) => {
    try {
      const updated = await updateSettings({ [key]: value });
      const next = { ...localStatus, ...updated };
      setLocalStatus(next);
      onStatusChange(next);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update");
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectStrava();
      onStatusChange(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to disconnect");
    }
  };

  const handleCreateMcpKey = async () => {
    try {
      const created = await createMcpApiKey(mcpKeyName);
      setNewMcpKey(created.api_key ?? null);
      setMcpKeys((current) => [created, ...current]);
      setMessage(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to generate MCP key");
    }
  };

  const handleRevokeMcpKey = async (id: number) => {
    try {
      await revokeMcpApiKey(id);
      setMcpKeys((current) => current.filter((key) => key.id !== id));
      setMessage(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to revoke MCP key");
    }
  };

  const claudeConfig = `{
  "mcpServers": {
    "strava-vps": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/proxy-server", "https://strava.andrewallkin.cloud/mcp/sse"],
      "env": {
        "HTTP_HEADERS": "{\\"Authorization\\": \\"Bearer YOUR_KEY\\"}"
      }
    }
  }
}`;

  return (
    <div className="max-w-2xl space-y-4">
      {message && (
        <div
          role="alert"
          className="rounded-lg px-4 py-3 text-sm font-medium bg-red-50 text-red-700 border border-red-200"
        >
          {message}
        </div>
      )}

      {/* Automations card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 divide-y divide-gray-100">
        <div className="px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-900">Automations</h2>
        </div>

        <div className="px-5 py-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-900">Run shoe selection</p>
            <p className="text-xs text-gray-500 mt-0.5">
              Ask via Telegram which shoes you used after a run.
            </p>
          </div>
          <Toggle
            id="run-shoe-toggle"
            checked={localStatus.run_shoe_enabled}
            onChange={(val) => handleToggle("run_shoe_enabled", val)}
          />
        </div>

        <div className="px-5 py-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-900">Gym hide from home</p>
            <p className="text-xs text-gray-500 mt-0.5">
              Auto-hide strength workouts from your Strava feed.
            </p>
          </div>
          <Toggle
            id="gym-hide-toggle"
            checked={localStatus.gym_hide_enabled}
            onChange={(val) => handleToggle("gym_hide_enabled", val)}
          />
        </div>
      </div>

      {/* MCP */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 divide-y divide-gray-100">
        <div className="px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-900">MCP access</h2>
          <p className="text-xs text-gray-500 mt-1">
            Generate a bearer token for Claude Desktop or another MCP client. The token can only read
            activities for your connected Strava athlete.
          </p>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              value={mcpKeyName}
              onChange={(event) => setMcpKeyName(event.target.value)}
              placeholder="Key name"
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
            <button
              type="button"
              onClick={handleCreateMcpKey}
              className="px-4 py-2 text-sm font-medium text-white bg-orange-500 rounded-md hover:bg-orange-600 transition-colors"
            >
              Generate key
            </button>
          </div>

          {newMcpKey && (
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-3">
              <p className="text-xs font-medium text-orange-900">
                Copy this key now. It will not be shown again.
              </p>
              <div className="mt-2 flex gap-2">
                <code className="flex-1 break-all rounded bg-white px-2 py-1 text-xs text-gray-800">
                  {newMcpKey}
                </code>
                <button
                  type="button"
                  onClick={() => navigator.clipboard?.writeText(newMcpKey)}
                  className="px-3 py-1 text-xs font-medium text-orange-700 bg-white border border-orange-200 rounded-md hover:bg-orange-100"
                >
                  Copy
                </button>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {mcpKeys.length === 0 ? (
              <p className="text-xs text-gray-500">No MCP keys yet.</p>
            ) : (
              mcpKeys.map((key) => (
                <div key={key.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{key.name || "Unnamed key"}</p>
                    <p className="text-xs text-gray-500">
                      Prefix {key.key_prefix} - Created {key.created_at ? new Date(key.created_at).toLocaleString() : "unknown"}
                      {key.last_used_at ? ` - Last used ${new Date(key.last_used_at).toLocaleString()}` : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRevokeMcpKey(key.id)}
                    className="px-3 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-md hover:bg-red-100"
                  >
                    Revoke
                  </button>
                </div>
              ))
            )}
          </div>

          <div>
            <p className="text-xs font-medium text-gray-700 mb-1">Claude Desktop proxy example</p>
            <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
              {claudeConfig}
            </pre>
          </div>
        </div>
      </div>

      {/* Disconnect */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-5 py-4">
        <h2 className="text-sm font-semibold text-gray-900 mb-3">Danger Zone</h2>
        <button
          type="button"
          onClick={handleDisconnect}
          className="px-4 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 transition-colors"
        >
          Disconnect Strava
        </button>
      </div>
    </div>
  );
}

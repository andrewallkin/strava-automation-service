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

/** Clipboard API can fail silently over HTTP or without permission; fall back to execCommand. */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

/** Claude Desktop / mcp-remote: Bearer token in env (keeps the secret out of CLI args). */
const MCP_CLIENT_JSON = `{
  "mcpServers": {
    "strava-vps-remote": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://strava.andrewallkin.cloud/mcp/sse",
        "--transport",
        "sse-only",
        "--header",
        "Authorization:\${STRAVA_MCP_AUTH_HEADER}"
      ],
      "env": {
        "STRAVA_MCP_AUTH_HEADER": "Bearer YOUR_SVA_MCP_KEY_HERE"
      }
    }
  }
}`;

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

type CopyNotice = { ok: boolean; text: string };

type SettingsPageProps = {
  status: Status;
  onStatusChange: (s: Status | null) => void;
};

export function SettingsPage({ status, onStatusChange }: SettingsPageProps) {
  const [localStatus, setLocalStatus] = useState<Status>(status);
  const [message, setMessage] = useState<string | null>(null);
  const [mcpKeys, setMcpKeys] = useState<McpApiKey[]>([]);
  const [newMcpKey, setNewMcpKey] = useState<string | null>(null);
  const [mcpKeyName, setMcpKeyName] = useState("");
  const [mcpKeyCopyNotice, setMcpKeyCopyNotice] = useState<CopyNotice | null>(null);
  const [mcpConfigCopyNotice, setMcpConfigCopyNotice] = useState<CopyNotice | null>(null);

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
    const trimmed = mcpKeyName.trim();
    if (!trimmed) return;
    try {
      const created = await createMcpApiKey(trimmed);
      setNewMcpKey(created.api_key ?? null);
      setMcpKeys((current) => [created, ...current]);
      setMessage(null);
      setMcpKeyCopyNotice(null);
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

  const canGenerateMcpKey = mcpKeyName.trim().length > 0;

  return (
    <div className="w-full space-y-4">
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
            Generate an API key for Claude Desktop (or any MCP client that uses the same JSON shape) with{" "}
            <code className="text-gray-700">mcp-remote</code>. Keys can only read activities for your connected
            Strava athlete (same tools as the hosted MCP server).
          </p>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              value={mcpKeyName}
              onChange={(event) => setMcpKeyName(event.target.value)}
              placeholder="e.g. Work laptop"
              aria-label="Key name"
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
            <button
              type="button"
              disabled={!canGenerateMcpKey}
              onClick={handleCreateMcpKey}
              className="px-4 py-2 text-sm font-medium text-white bg-orange-500 rounded-md hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-orange-500"
            >
              Generate key
            </button>
          </div>

          {newMcpKey && (
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-3">
              <p className="text-xs font-medium text-orange-900">
                Copy this key now. It will not be shown again.
              </p>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-stretch">
                <code
                  id="new-mcp-key-value"
                  className="flex-1 break-all rounded bg-white px-2 py-1 text-xs text-gray-800"
                >
                  {newMcpKey}
                </code>
                <button
                  type="button"
                  onClick={async () => {
                    const ok = await copyToClipboard(newMcpKey);
                    setMcpKeyCopyNotice(
                      ok
                        ? { ok: true, text: "Key copied." }
                        : {
                            ok: false,
                            text: "Could not copy automatically — select the key above and press ⌘C / Ctrl+C."
                          }
                    );
                  }}
                  className="px-3 py-1 text-xs font-medium text-orange-700 bg-white border border-orange-200 rounded-md hover:bg-orange-100 shrink-0 self-start sm:self-auto"
                >
                  Copy key
                </button>
              </div>
              {mcpKeyCopyNotice && (
                <p
                  className={`mt-2 text-xs ${mcpKeyCopyNotice.ok ? "text-green-800" : "text-orange-900"}`}
                  role="status"
                >
                  {mcpKeyCopyNotice.text}
                </p>
              )}
            </div>
          )}

          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-700">Your keys</p>
            {mcpKeys.length === 0 ? (
              <p className="text-xs text-gray-500">No MCP keys yet.</p>
            ) : (
              mcpKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between rounded-lg border border-gray-200 bg-gray-50/50 px-3 py-3"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    <p className="text-sm font-medium text-gray-900">{key.name || "Unnamed key"}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] font-medium uppercase tracking-wide text-gray-500">
                        Prefix
                      </span>
                      <code className="rounded-md bg-white px-2 py-0.5 text-xs text-gray-800 border border-gray-200 font-mono">
                        {key.key_prefix}
                      </code>
                    </div>
                    <div className="grid gap-1 text-xs text-gray-600 sm:grid-cols-2 sm:gap-x-4">
                      <p>
                        <span className="text-gray-500">Created</span>{" "}
                        {key.created_at ? new Date(key.created_at).toLocaleString() : "—"}
                      </p>
                      <p>
                        <span className="text-gray-500">Last used</span>{" "}
                        {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never used"}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRevokeMcpKey(key.id)}
                    className="w-full shrink-0 px-3 py-1.5 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 sm:w-auto sm:self-center"
                  >
                    Revoke
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 space-y-2">
            <h3 className="text-xs font-semibold text-gray-900">Claude Desktop setup</h3>
            <ol className="list-decimal list-inside space-y-2 text-xs text-gray-600">
              <li>
                <span className="font-medium text-gray-800">Generate a key</span> above and copy it when the
                orange box appears — you will not see the full secret again.
              </li>
              <li>
                <span className="font-medium text-gray-800">Open </span>
                <code className="text-gray-800">claude_desktop_config.json</code>
                <span className="font-medium text-gray-800">:</span>
                <ul className="mt-1.5 ml-4 list-disc list-inside space-y-1.5 text-gray-600">
                  <li>
                    <span className="text-gray-800">macOS:</span> In Claude Desktop, choose{" "}
                    <span className="text-gray-800">Settings → Developer → Edit Config</span>. Or in Finder:{" "}
                    <span className="text-gray-800">Go → Go to Folder…</span> (⌘⇧G), paste{" "}
                    <code className="text-gray-800">~/Library/Application Support/Claude</code>, then open{" "}
                    <code className="text-gray-800">claude_desktop_config.json</code>.
                  </li>
                  <li>
                    <span className="text-gray-800">Windows:</span> Press <kbd className="rounded border border-gray-300 bg-white px-1">Win</kbd>+
                    <kbd className="rounded border border-gray-300 bg-white px-1">R</kbd>, type{" "}
                    <code className="text-gray-800">%APPDATA%\Claude</code>, press Enter, then open{" "}
                    <code className="text-gray-800">claude_desktop_config.json</code> (you can also paste that
                    path into File Explorer’s address bar).
                  </li>
                </ul>
              </li>
              <li>
                <span className="font-medium text-gray-800">Merge</span> the <code className="text-gray-800">strava-vps-remote</code>{" "}
                entry from the snippet below into your file’s <code className="text-gray-800">mcpServers</code>{" "}
                object. If <code className="text-gray-800">mcpServers</code> already exists, add this server alongside your others — do not remove unrelated servers.
              </li>
              <li>
                <span className="font-medium text-gray-800">Quit and restart Claude Desktop</span> fully so MCP
                reloads.
              </li>
            </ol>
          </div>

          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <p className="text-xs font-medium text-gray-700">
                Configuration snippet (<code className="text-gray-600">claude_desktop_config.json</code>)
              </p>
              <button
                type="button"
                onClick={async () => {
                  const ok = await copyToClipboard(MCP_CLIENT_JSON);
                  setMcpConfigCopyNotice(
                    ok
                      ? { ok: true, text: "Config JSON copied." }
                      : {
                          ok: false,
                          text: "Could not copy automatically — select the JSON below and copy manually."
                        }
                  );
                }}
                className="px-2.5 py-1 text-xs font-medium text-gray-700 bg-gray-100 border border-gray-200 rounded-md hover:bg-gray-200"
              >
                Copy JSON
              </button>
            </div>
            <ul className="text-xs text-gray-600 mb-2 space-y-1 list-disc list-inside">
              <li>
                Use <strong className="font-medium text-gray-800">Copy JSON</strong> or select the block below.
              </li>
              <li>
                Replace <code className="text-gray-800">YOUR_SVA_MCP_KEY_HERE</code> with your full key (the{" "}
                <code className="text-gray-800">sva_mcp_…</code> value). Keep the <code className="text-gray-800">Bearer </code>
                prefix in <code className="text-gray-800">STRAVA_MCP_AUTH_HEADER</code>.
              </li>
              <li>
                The key lives in <code className="text-gray-800">env</code> so it is not passed as a separate CLI argument.
              </li>
            </ul>
            {mcpConfigCopyNotice && (
              <p
                className={`text-xs mb-2 ${mcpConfigCopyNotice.ok ? "text-green-800" : "text-orange-900"}`}
                role="status"
              >
                {mcpConfigCopyNotice.text}
              </p>
            )}
            <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
              {MCP_CLIENT_JSON}
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

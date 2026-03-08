import { useState } from "react";
import { Status, disconnectStrava, updateSettings } from "../lib/api";

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

  return (
    <div className="max-w-lg space-y-4">
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

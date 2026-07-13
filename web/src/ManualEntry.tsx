import { FormEvent, useState } from "react";

import { apiFetch } from "./api";
import type { Provider } from "./types";

function localDateTime(iso: string | null | undefined) {
  if (!iso) return "";
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

const CADENCE = /^(daily:\s*\d{1,2}:\d{2}|weekly:(mon|tue|wed|thu|fri|sat|sun)\s+\d{1,2}:\d{2})$/;

export function ManualEntry({
  provider,
  onSaved,
}: {
  provider: Provider;
  onSaved: () => Promise<void>;
}) {
  const current = provider.windows[0];
  const [used, setUsed] = useState(
    current?.used_pct == null ? "" : String(current.used_pct),
  );
  const [reset, setReset] = useState(localDateTime(current?.resets_at));
  const [cadence, setCadence] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = Number(used);
    if (!Number.isFinite(value) || value < 0 || value > 100) {
      setMessage("Enter a percentage from 0 to 100.");
      return;
    }
    if (reset && cadence) {
      setMessage("Use either an exact reset or a cadence, not both.");
      return;
    }
    if (cadence && !CADENCE.test(cadence.trim().toLowerCase())) {
      setMessage("Use daily: HH:MM or weekly:day HH:MM, such as weekly:thu 23:59.");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const response = await apiFetch(`/api/v1/providers/${provider.id}/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          windows: [
            {
              name: current?.name ?? "weekly",
              quota_state: "metered",
              used_pct: value,
              resets_at: reset ? new Date(reset).toISOString() : null,
              cadence: reset ? null : cadence.trim().toLowerCase() || null,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
              estimated: true,
            },
          ],
        }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Update failed (${response.status})`);
      }
      setMessage("Manual quota updated.");
      await onSaved();
    } catch (cause) {
      setMessage(
        cause instanceof Error ? cause.message : "Manual quota could not be updated.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="manual-entry" onSubmit={submit} noValidate>
      <label htmlFor={`manual-${provider.id}`}>Used percentage</label>
      <div>
        <input
          id={`manual-${provider.id}`}
          inputMode="decimal"
          type="number"
          min="0"
          max="100"
          step="0.1"
          value={used}
          onChange={(event) => setUsed(event.target.value)}
          aria-describedby={`manual-help-${provider.id}`}
        />
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Update"}
        </button>
      </div>
      <details className="manual-schedule">
        <summary>Reset schedule (optional)</summary>
        <label htmlFor={`manual-reset-${provider.id}`}>Exact reset</label>
        <input
          id={`manual-reset-${provider.id}`}
          type="datetime-local"
          value={reset}
          onChange={(event) => {
            setReset(event.target.value);
            if (event.target.value) setCadence("");
          }}
        />
        <span>or</span>
        <label htmlFor={`manual-cadence-${provider.id}`}>Recurring cadence</label>
        <input
          id={`manual-cadence-${provider.id}`}
          type="text"
          value={cadence}
          onChange={(event) => {
            setCadence(event.target.value);
            if (event.target.value) setReset("");
          }}
          placeholder="weekly:thu 23:59"
        />
      </details>
      <small id={`manual-help-${provider.id}`}>
        Enter the value shown by the provider. Recurring times use your browser timezone.
      </small>
      {message && (
        <span className="form-message" role="status">
          {message}
        </span>
      )}
    </form>
  );
}

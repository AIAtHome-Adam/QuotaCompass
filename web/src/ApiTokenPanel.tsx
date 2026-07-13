import { useState } from "react";

import { hasApiToken, setApiToken } from "./api";

export function ApiTokenPanel({ onSaved }: { onSaved: () => Promise<void> }) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setApiToken(value);
    setSaving(true);
    try {
      await onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="api-token-panel" onSubmit={submit}>
      <div>
        <strong>API authentication required</strong>
        <span>The token stays in this browser tab and is sent only to this QuotaCompass origin.</span>
      </div>
      <label htmlFor="api-token" className="sr-only">QuotaCompass API token</label>
      <input
        id="api-token"
        type="password"
        autoComplete="off"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={hasApiToken() ? "Replace saved session token" : "API bearer token"}
        required
      />
      <button type="submit" disabled={saving}>{saving ? "Checking…" : "Connect"}</button>
    </form>
  );
}

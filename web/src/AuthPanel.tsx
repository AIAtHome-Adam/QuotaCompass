import { useState } from "react";

import { reauthFetch } from "./api";
import type { Provider } from "./types";

const order: Record<string, number> = {
  expired: 0,
  error: 1,
  expiring_soon: 2,
  unknown: 3,
  ok: 4,
};

export function AuthPanel({ providers }: { providers: Provider[] }) {
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reauthTarget, setReauthTarget] = useState<string | null>(null);
  const [reauthToken, setReauthToken] = useState("");
  const attention = [...providers]
    .filter((provider) => provider.auth.status !== "ok")
    .sort((left, right) => (order[left.auth.status] ?? 9) - (order[right.auth.status] ?? 9));
  const target = attention.find((provider) => provider.id === reauthTarget) ?? null;

  async function reauthenticate(provider: Provider, token = "") {
    setPending(provider.id);
    setMessage(null);
    try {
      const response = await reauthFetch(
        `/api/v1/providers/${encodeURIComponent(provider.id)}/reauth`,
        token,
      );
      if (response.status === 401 && !token) {
        setReauthTarget(provider.id);
        setMessage("Remote reauthentication requires its separate authorization token.");
        return;
      }
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Request failed (${response.status})`);
      }
      setReauthTarget(null);
      setMessage(`${provider.label} login started in the native provider flow.`);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Login could not be started.");
    } finally {
      setPending(null);
      if (token) setReauthToken("");
    }
  }

  if (attention.length === 0) return null;
  return (
    <section aria-labelledby="auth-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Account health</p>
          <h2 id="auth-title">Authentication attention</h2>
        </div>
      </div>
      <div className="auth-list">
        {attention.map((provider) => (
          <article key={provider.id}>
            <span className={`auth-dot auth-${provider.auth.status}`} aria-hidden="true" />
            <div>
              <strong>{provider.label}</strong>
              <span>
                {provider.auth.status.replaceAll("_", " ")}
                {provider.auth.expires_at
                  ? ` - ${new Date(provider.auth.expires_at).toLocaleString()}`
                  : ""}
              </span>
            </div>
            {provider.auth.reauth?.automatable ? (
              <button
                type="button"
                disabled={pending !== null}
                onClick={() => void reauthenticate(provider)}
                aria-label={`Start native login for ${provider.label}`}
              >
                {pending === provider.id ? "Starting..." : "Reauthenticate"}
              </button>
            ) : (
              <code>Check provider sign-in</code>
            )}
          </article>
        ))}
      </div>

      {target ? (
        <form
          className="reauth-token-panel"
          onSubmit={(event) => {
            event.preventDefault();
            void reauthenticate(target, reauthToken);
          }}
        >
          <div>
            <label htmlFor="reauth-token">Separate reauthentication token</label>
            <small>
              Required only for a remote trigger. It stays in this form's memory for one attempt
              and is never saved in browser storage.
            </small>
          </div>
          <input
            id="reauth-token"
            type="password"
            autoComplete="off"
            value={reauthToken}
            onChange={(event) => setReauthToken(event.target.value)}
            required
          />
          <button type="submit" disabled={pending !== null}>Authorize reauthentication</button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setReauthTarget(null);
              setReauthToken("");
              setMessage(null);
            }}
          >
            Cancel
          </button>
        </form>
      ) : null}
      {message ? <p className="auth-message" role="status">{message}</p> : null}
    </section>
  );
}

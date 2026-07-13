import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ManualEntry } from "./ManualEntry";
import { HistoryPanel } from "./HistoryPanel";
import { AuthPanel } from "./AuthPanel";
import { ApiTokenPanel } from "./ApiTokenPanel";
import { ResetTimeline } from "./ResetTimeline";
import { apiFetch } from "./api";
import type { LimitWindow, Provider, Snapshot } from "./types";

const statusCopy: Record<string, { label: string; icon: string }> = {
  ok: { label: "Current", icon: "check" },
  stale: { label: "Last known", icon: "clock" },
  error: { label: "Could not check", icon: "alert" },
  expired: { label: "Sign-in required", icon: "key" },
  expiring_soon: { label: "Sign-in expires soon", icon: "clock" },
};

function Icon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    check: <path d="m5 12 4 4L19 6" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    alert: <><path d="M12 3 2.8 20h18.4L12 3Z" /><path d="M12 9v4m0 3h.01" /></>,
    key: <><circle cx="8" cy="15" r="4" /><path d="m11 12 8-8m-3 3 2 2" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" /></>,
    refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 5v6h-6" /></>,
    moon: <path d="M20 15.5A8 8 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z" />,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    external: <><path d="M14 5h5v5M19 5l-8 8" /><path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

const repositoryUrl = "https://github.com/AIAtHome-Adam/QuotaCompass";

const resourceGroups = [
  {
    id: "help-links",
    title: "Help & documentation",
    links: [
      { label: "Getting started", detail: "Install, setup, and everyday commands", href: repositoryUrl + "#install-and-start" },
      { label: "Troubleshooting", detail: "Resolve setup, sign-in, and refresh issues", href: repositoryUrl + "/blob/main/docs/TROUBLESHOOTING.md" },
      { label: "Customization", detail: "Tune polling, history, providers, and nudges", href: repositoryUrl + "/blob/main/docs/CUSTOMIZATION.md" },
      { label: "Provider support", detail: "Capabilities, fallbacks, and verification", href: repositoryUrl + "/blob/main/docs/PROVIDERS.md" },
      { label: "Local API reference", detail: "Interactive reference for this server", href: "/docs" },
    ],
  },
  {
    id: "community-links",
    title: "Connect",
    links: [
      { label: "YouTube", detail: "AI at Home with Adam", href: "https://www.youtube.com/@aiathome-adam" },
      { label: "GitHub", detail: "Projects from AI at Home", href: "https://github.com/AIAtHome-Adam" },
      { label: "X", detail: "Updates and release notes", href: "https://x.com/AIAtHome_Adam" },
      { label: "Buy Me a Coffee", detail: "Support future development", href: "https://buymeacoffee.com/aiathomeadam" },
      { label: "LinkedIn", detail: "Connect with Adam Ellch", href: "https://www.linkedin.com/in/adam-ellch" },
    ],
  },
] as const;

function ResourceMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="resource-menu" ref={containerRef}>
      <button
        ref={buttonRef}
        type="button"
        className={"icon-button" + (open ? " is-active" : "")}
        aria-label={(open ? "Close" : "Open") + " resources menu"}
        aria-expanded={open}
        aria-controls="resource-menu-panel"
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="menu" />
      </button>
      {open && (
        <nav id="resource-menu-panel" className="resource-panel" aria-label="Resources and community">
          {resourceGroups.map((group) => (
            <section className="resource-group" aria-labelledby={group.id} key={group.id}>
              <h2 id={group.id}>{group.title}</h2>
              <ul>
                {group.links.map((link) => (
                  <li key={link.href}>
                    <a href={link.href} target="_blank" rel="noreferrer">
                      <span><strong>{link.label}</strong><small>{link.detail}</small></span>
                      <Icon name="external" />
                      <span className="sr-only"> (opens in a new tab)</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </nav>
      )}
    </div>
  );
}

function relativeTime(value: string | null, now: number) {
  if (!value) return "No reset reported";
  const seconds = Math.max(0, Math.round((new Date(value).getTime() - now) / 1000));
  if (seconds < 3600) return `in ${Math.ceil(seconds / 60)}m`;
  if (seconds < 86400) return `in ${Math.floor(seconds / 3600)}h ${Math.ceil((seconds % 3600) / 60)}m`;
  return `in ${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

function available(window: LimitWindow) {
  if (window.quota_state === "unlimited") return window.temporary ? "Temporarily unmetered" : "Unlimited";
  if (window.used_pct == null) return window.quota_state === "unavailable" ? "Unavailable" : "Unknown";
  return `${Math.round(100 - window.used_pct)}% available`;
}

function WindowBar({ window, now }: { window: LimitWindow; now: number }) {
  const remaining = window.used_pct == null ? 0 : 100 - window.used_pct;
  const measurable = window.used_pct != null || window.quota_state === "unlimited";
  const semanticRemaining = window.quota_state === "unlimited" ? 100 : remaining;
  return (
    <div className={`window-row${window.temporary ? " window-temporary" : ""}`}>
      <div className="window-copy">
        <span className="window-name">{window.name}</span>
        <strong>{available(window)}</strong>
        <span>{window.status_note ?? relativeTime(window.resets_at, now)}{window.estimated ? " · estimated" : ""}</span>
      </div>
      <div
        className={`meter meter-${window.quota_state}`}
        role={measurable ? "meter" : "img"}
        aria-label={`${window.name}: ${available(window)}`}
        aria-valuemin={measurable ? 0 : undefined}
        aria-valuemax={measurable ? 100 : undefined}
        aria-valuenow={measurable ? semanticRemaining : undefined}
      >
        <span style={{ width: `${remaining}%` }} />
      </div>
    </div>
  );
}

function ProviderCard({ provider, now, onUpdated }: { provider: Provider; now: number; onUpdated: () => Promise<void> }) {
  const state = provider.auth.status === "expired" ? "expired" : provider.fetch_status;
  const status = statusCopy[state] ?? statusCopy.error;
  return (
    <article className={`provider-card state-${state}`} aria-labelledby={`provider-${provider.id}`}>
      <header>
        <div>
          <p className="eyebrow">{provider.support_tier} · {provider.data_source.replaceAll("_", " ")}</p>
          <h3 id={`provider-${provider.id}`}>{provider.label}</h3>
        </div>
        <span className="status-chip"><Icon name={status.icon} />{status.label}</span>
      </header>
      {provider.capacity_notices?.map((notice) => (
        <div className="capacity-notice" role="status" key={notice.notice_id}>
          <Icon name="compass" />
          <span><strong>{notice.title}</strong>{notice.message}</span>
        </div>
      ))}
      <div className="windows">
        {provider.windows.length ? provider.windows.map((window) => (
          <WindowBar key={window.window_id} window={window} now={now} />
        )) : <p className="empty">No quota windows are available.</p>}
      </div>
      {provider.fetch_error && (
        <p className="recovery" role="status"><Icon name="alert" />
          <span>{provider.fetch_error.message}{provider.fetch_error.user_action ? ` · ${provider.fetch_error.user_action}` : ""}</span>
        </p>
      )}
      <HistoryPanel provider={provider} />
      {(provider.data_source === "manual" || provider.fetch_status !== "ok") && (
        <ManualEntry provider={provider} onSaved={onUpdated} />
      )}
    </article>
  );
}

export function App() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now());
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");

  const load = useCallback(async () => {
    setError(null);
    try {
      const response = await apiFetch("/api/v1/status", { headers: { Accept: "application/json" } });
      if (!response.ok) {
        setAuthRequired(response.status === 401);
        throw new Error(`Status request failed (${response.status})`);
      }
      setAuthRequired(false);
      setData(await response.json());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Quota data could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); const poll = setInterval(load, 60_000); return () => clearInterval(poll); }, [load]);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; localStorage.setItem("theme", dark ? "dark" : "light"); }, [dark]);

  const recommendation = useMemo(() => data?.advisor.ranking.find((item) => item.id === data.advisor.suggestion), [data]);
  const recommendedProvider = data?.providers.find((item) => item.id === data.advisor.suggestion);

  return (
    <>
      <a className="skip-link" href="#main">Skip to quota overview</a>
      <header className="topbar">
        <a className="brand" href="/" aria-label="QuotaCompass home"><Icon name="compass" /><span>QuotaCompass</span></a>
        <div className="top-actions">
          {data && <span className="updated">Updated {new Date(data.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>}
          <button type="button" className="icon-button" onClick={() => void load()} aria-label="Refresh quota data"><Icon name="refresh" /></button>
          <button type="button" className="icon-button" onClick={() => setDark((value) => !value)} aria-label={`Use ${dark ? "light" : "dark"} theme`}><Icon name="moon" /></button>
          <ResourceMenu />
        </div>
      </header>
      <main id="main" className="shell">
        {loading && <div className="loading" role="status">Reading local quota state…</div>}
        {error && <div className="error-banner" role="alert"><Icon name="alert" /><span>{error}. Existing cards are preserved during background refreshes.</span><button onClick={() => void load()}>Retry</button></div>}
        {authRequired && <ApiTokenPanel onSaved={load} />}
        {data && (
          <>
            <section className="recommendation" aria-labelledby="recommend-title">
              <div className="compass-mark"><Icon name="compass" /></div>
              <div>
                <p className="eyebrow">Best lane right now</p>
                <h1 id="recommend-title">Use {recommendedProvider?.label ?? "your available provider"}</h1>
                <p>{recommendation?.reason ?? "QuotaCompass is comparing available windows."}</p>
              </div>
              <div className="score"><strong>{recommendation ? Math.max(0, Math.round(recommendation.score * 100)) : "—"}</strong><span>balance score</span></div>
            </section>

            {data.advisor.expiring_unused.length > 0 && (
              <section aria-labelledby="nudges-title">
                <div className="section-heading"><div><p className="eyebrow">Use it or lose it</p><h2 id="nudges-title">Quota expiring soon</h2></div></div>
                <div className="nudge-grid">{data.advisor.expiring_unused.map((item) => (
                  <article className="nudge" key={`${item.id}-${item.window}`}><Icon name="clock" /><div><strong>{item.note}</strong><span>{new Date(item.resets_at).toLocaleString()}</span></div></article>
                ))}</div>
              </section>
            )}

            <AuthPanel providers={data.providers} />

            <section aria-labelledby="providers-title">
              <div className="section-heading"><div><p className="eyebrow">All lanes</p><h2 id="providers-title">Provider overview</h2></div><span>{data.providers.length} configured</span></div>
              <div className="provider-grid">{data.providers.map((provider) => <ProviderCard key={provider.id} provider={provider} now={now} onUpdated={load} />)}</div>
            </section>

            <section className="schedule" aria-labelledby="schedule-title">
              <div className="section-heading"><div><p className="eyebrow">Next seven days</p><h2 id="schedule-title">Reset horizon</h2></div></div>
              <ResetTimeline providers={data.providers} now={now} />
            </section>
          </>
        )}
      </main>
      <div className="sr-only" aria-live="polite">{loading ? "Refreshing quota data" : error ?? "Quota data is current"}</div>
    </>
  );
}

import { useEffect, useMemo, useState } from "react";

import type { Provider } from "./types";

const HORIZON_MS = 7 * 24 * 60 * 60 * 1000;
const COLLISION_MS = 60 * 60 * 1000;

interface ResetEvent {
  id: string;
  providerId: string;
  provider: string;
  window: string;
  iso: string;
  at: number;
}

function resetEvents(providers: Provider[], now: number): ResetEvent[] {
  const end = now + HORIZON_MS;
  return providers
    .flatMap((provider) =>
      provider.windows.flatMap((window) => {
        if (!window.resets_at) return [];
        const at = new Date(window.resets_at).getTime();
        if (!Number.isFinite(at) || at < now || at > end) return [];
        return [{
          id: provider.id + ":" + window.window_id + ":" + window.resets_at,
          providerId: provider.id,
          provider: provider.label,
          window: window.name,
          iso: window.resets_at,
          at,
        }];
      }),
    )
    .sort((left, right) => left.at - right.at);
}

function collisionGroups(events: ResetEvent[]): ResetEvent[][] {
  const groups: ResetEvent[][] = [];
  for (const event of events) {
    const current = groups.at(-1);
    if (current && event.at - current[0].at <= COLLISION_MS) current.push(event);
    else groups.push([event]);
  }
  return groups;
}

function relativeReset(at: number, now: number) {
  const minutes = Math.max(0, Math.round((at - now) / 60000));
  if (minutes < 60) return "in " + minutes + "m";
  if (minutes < 1440) return "in " + Math.floor(minutes / 60) + "h " + (minutes % 60) + "m";
  return "in " + Math.floor(minutes / 1440) + "d " + Math.floor((minutes % 1440) / 60) + "h";
}

export function ResetTimeline({ providers, now }: { providers: Provider[]; now: number }) {
  const [selected, setSelected] = useState("all");
  const allEvents = useMemo(() => resetEvents(providers, now), [providers, now]);
  const options = useMemo(
    () => providers.filter((provider) => allEvents.some((event) => event.providerId === provider.id)),
    [providers, allEvents],
  );

  useEffect(() => {
    if (selected !== "all" && !options.some((provider) => provider.id === selected)) setSelected("all");
  }, [options, selected]);

  const events = selected === "all"
    ? allEvents
    : allEvents.filter((event) => event.providerId === selected);
  const groups = collisionGroups(events);
  const collisionSize = new Map<string, number>();
  for (const group of groups) {
    for (const event of group) collisionSize.set(event.id, group.length);
  }
  const collisionCount = groups.filter((group) => group.length > 1).length;
  const days = Array.from({ length: 8 }, (_, index) => {
    const date = new Date(now + index * 24 * 60 * 60 * 1000);
    return index === 0
      ? "Now"
      : date.toLocaleDateString([], { weekday: "short", day: "numeric" });
  });

  return (
    <>
      <div className="timeline-controls" role="group" aria-label="Filter reset timeline by provider">
        <button type="button" aria-pressed={selected === "all"} onClick={() => setSelected("all")}>
          All providers
        </button>
        {options.map((provider) => (
          <button
            type="button"
            aria-pressed={selected === provider.id}
            onClick={() => setSelected(provider.id)}
            key={provider.id}
          >
            {provider.label}
          </button>
        ))}
      </div>

      <p className="timeline-summary" aria-live="polite">
        {events.length
          ? events.length + (events.length === 1 ? " reset" : " resets") + " in the next seven days" + (collisionCount ? "; " + collisionCount + " collision " + (collisionCount === 1 ? "group" : "groups") : "")
          : "No resets match this filter in the next seven days."}
      </p>

      {events.length > 0 ? (
        <>
          <div
            className="reset-timeline"
            role="img"
            aria-label={"Seven-day reset timeline showing " + events.length + " events. Exact values follow in chronological order."}
          >
            <div className="timeline-track" aria-hidden="true">
              {groups.map((group, index) => {
                const position = Math.max(0, Math.min(100, ((group[0].at - now) / HORIZON_MS) * 100));
                const edge = position < 12 ? "start" : position > 88 ? "end" : "middle";
                return (
                  <span
                    className="timeline-marker"
                    data-edge={edge}
                    style={{ left: position + "%", top: 16 + (index % 3) * 38 + "px" }}
                    key={group.map((event) => event.id).join("|")}
                  >
                    <span className="timeline-dot" />
                    <span className="timeline-label">
                      {group.length > 1 ? group.length + " resets" : group[0].provider}
                    </span>
                  </span>
                );
              })}
            </div>
            <div className="timeline-axis" aria-hidden="true">
              {days.map((day, index) => <span key={index}>{day}</span>)}
            </div>
          </div>

          <ol className="agenda timeline-agenda">
            {events.map((event) => {
              const nearby = collisionSize.get(event.id) ?? 1;
              return (
                <li key={event.id}>
                  <time dateTime={event.iso}>
                    {new Date(event.at).toLocaleString([], {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </time>
                  <span>
                    <strong>{event.provider}</strong>
                    <small>{event.window} resets {relativeReset(event.at, now)}</small>
                    {nearby > 1 ? <em>{nearby} resets occur within one hour</em> : null}
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      ) : (
        <p className="timeline-empty">Choose another provider or wait for a provider to report its next reset.</p>
      )}
    </>
  );
}

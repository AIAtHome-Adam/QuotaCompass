import { useState } from "react";
import { apiFetch } from "./api";
import type { Provider } from "./types";

interface HistoryPoint {
  time: string;
  value: number;
  window: string;
}

function points(history: Provider[]): HistoryPoint[] {
  return history.flatMap((provider) => {
    const window = provider.windows.find((item) => item.used_pct != null);
    return window?.used_pct == null || !provider.last_success_at
      ? []
      : [{ time: provider.last_success_at, value: window.used_pct, window: window.name }];
  });
}

function xPosition(index: number, count: number) {
  return count === 1 ? 50 : (index / (count - 1)) * 100;
}

function inferredResetIndexes(values: HistoryPoint[]) {
  const indexes = new Set<number>();
  for (let index = 1; index < values.length; index++) {
    if (values[index - 1].value - values[index].value >= 5) indexes.add(index);
  }
  return indexes;
}

export function HistoryPanel({ provider }: { provider: Provider }) {
  const [history, setHistory] = useState<Provider[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/providers/${provider.id}/history?days=30`);
      if (!response.ok) throw new Error(`History request failed (${response.status})`);
      setHistory(await response.json());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "History could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  const values = points(history ?? []);
  const boundaries = inferredResetIndexes(values);
  const path = values
    .map((item, index) => xPosition(index, values.length) + "," + (100 - item.value))
    .join(" ");
  const windowName = values[0]?.window ?? "metered";

  return (
    <details className="history-panel" onToggle={(event) => {
      if (event.currentTarget.open && history === null && !loading) void load();
    }}>
      <summary>30-day history</summary>
      {loading && <p role="status">Loading local history...</p>}
      {error && <p role="alert">{error} <button type="button" onClick={() => void load()}>Retry</button></p>}
      {history && values.length === 0 && <p>No metered history has been recorded yet.</p>}
      {values.length > 0 && (
        <>
          <svg
            className="sparkline"
            viewBox="0 0 100 100"
            role="img"
            aria-label={
              provider.label + " " + windowName + " usage history, from " +
              values[0].value.toFixed(1) + " to " + values.at(-1)!.value.toFixed(1) +
              " percent used, with " + boundaries.size + " inferred reset " +
              (boundaries.size === 1 ? "boundary" : "boundaries")
            }
            preserveAspectRatio="none"
          >
            <line x1="0" x2="100" y1="25" y2="25" />
            <line x1="0" x2="100" y1="50" y2="50" />
            <line x1="0" x2="100" y1="75" y2="75" />
            {[...boundaries].map((index) => {
              const x = xPosition(index, values.length);
              return (
                <line className="reset-boundary" x1={x} x2={x} y1="0" y2="100" key={values[index].time}>
                  <title>Reset inferred from usage returning to a lower value</title>
                </line>
              );
            })}
            <polyline points={path} />
          </svg>
          <div className="history-legend" aria-hidden="true">
            <span><i />Usage</span>
            <span><i className="reset-key" />Inferred reset</span>
          </div>
          <div className="history-table-wrap">
            <table>
              <caption className="sr-only">Exact recorded usage values and inferred reset boundaries</caption>
              <thead><tr><th scope="col">Recorded</th><th scope="col">Used</th><th scope="col">Event</th></tr></thead>
              <tbody>{values.map((item, index) => (
                <tr key={item.time + ":" + index}>
                  <td>{new Date(item.time).toLocaleString()}</td>
                  <td>{item.value.toFixed(1)}%</td>
                  <td>{boundaries.has(index) ? "Reset inferred" : ""}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </details>
  );
}

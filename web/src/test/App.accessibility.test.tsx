import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { Snapshot } from "../types";

const now = new Date("2026-07-12T20:00:00Z");
const later = new Date("2026-07-16T20:00:00Z");

const snapshot: Snapshot = {
  generated_at: now.toISOString(),
  providers: [
    {
      id: "codex",
      label: "ChatGPT / Codex",
      kind: "subscription",
      support_tier: "stable",
      data_source: "unofficial_api",
      auth: { status: "ok", expires_at: null },
      windows: [
        {
          window_id: "codex:18000-promotion",
          name: "5h",
          quota_state: "unlimited",
          used_pct: null,
          resets_at: null,
          resets_in_seconds: null,
          estimated: false,
          temporary: true,
          inferred: true,
          status_note: "5-hour limit is temporarily unmetered; the weekly limit still applies.",
        },
        {
          window_id: "codex:weekly",
          name: "weekly",
          quota_state: "metered",
          used_pct: 24,
          resets_at: later.toISOString(),
          resets_in_seconds: 345600,
          estimated: false,
          temporary: false,
          inferred: false,
          status_note: null,
        },
      ],
      capacity_notices: [
        {
          notice_id: "codex:short-window-unmetered",
          kind: "promotion",
          title: "Temporary capacity boost detected",
          message: "5-hour limit is temporarily unmetered; the weekly limit still applies.",
          temporary: true,
          inferred: true,
          confidence: "high",
          evidence: "valid_weekly_window_with_explicitly_null_secondary_window",
        },
      ],
      fetch_status: "ok",
      fetch_error: null,
      last_success_at: now.toISOString(),
    },
    {
      id: "manual-provider",
      label: "Manual provider",
      kind: "manual",
      support_tier: "stable",
      data_source: "manual",
      auth: { status: "unknown", expires_at: null },
      windows: [
        {
          window_id: "manual-provider:weekly",
          name: "weekly",
          quota_state: "metered",
          used_pct: 35,
          resets_at: later.toISOString(),
          resets_in_seconds: 345600,
          estimated: true,
          temporary: false,
          inferred: false,
          status_note: null,
        },
      ],
      capacity_notices: [],
      fetch_status: "ok",
      fetch_error: null,
      last_success_at: now.toISOString(),
    },
    {
      id: "cursor",
      label: "Cursor",
      kind: "subscription",
      support_tier: "beta",
      data_source: "unofficial_api",
      auth: {
        status: "expired",
        expires_at: now.toISOString(),
        reauth: { command: "cursor login", automatable: true },
      },
      windows: [],
      capacity_notices: [],
      fetch_status: "stale",
      fetch_error: {
        message: "Sign in to Cursor to refresh quota data",
        user_action: "Open Cursor and sign in",
      },
      last_success_at: null,
    },
  ],
  advisor: {
    suggestion: "codex",
    ranking: [
      {
        id: "codex",
        score: 0.72,
        reason: "Temporary unmetered 5h lane detected; 76% remains in the weekly limit",
        excluded: false,
      },
    ],
    expiring_unused: [],
  },
};

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const history = [60, 18].map((used, index) => ({
  ...snapshot.providers[0],
  last_success_at: new Date(now.getTime() + index * 60 * 60 * 1000).toISOString(),
  windows: snapshot.providers[0].windows.map((window, windowIndex) => (
    windowIndex === 0 ? { ...window, used_pct: used } : window
  )),
}));

describe("QuotaCompass dashboard accessibility", () => {
  const reauthHeaders: Array<string | null> = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const target = String(input);
    if (target === "/api/v1/status") return response(snapshot);
    if (target.includes("/history?")) return response(history);
    if (target.endsWith("/reauth")) {
      const authorization = new Headers(init?.headers).get("Authorization");
      reauthHeaders.push(authorization);
      return authorization === "Bearer reauth-secret"
        ? response({ status: "started", pid: 123, operation_id: "op" })
        : response({ detail: "Separate reauthentication token required" }, 401);
    }
    throw new Error("Unexpected request: " + target);
  });

  beforeEach(() => {
    fetchMock.mockClear();
    reauthHeaders.length = 0;
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("has no serious or critical axe violations in representative demo states", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Use ChatGPT / Codex" });
    await user.click(screen.getByRole("button", { name: "Start native login for Cursor" }));
    await screen.findByLabelText("Separate reauthentication token");
    const codexCard = screen.getByRole("heading", { name: "ChatGPT / Codex" }).closest("article");
    expect(codexCard).not.toBeNull();
    await user.click(within(codexCard!).getByText("30-day history"));
    await within(codexCard!).findByRole("cell", { name: "Reset inferred" });
    await user.click(screen.getByRole("button", { name: "Open resources menu" }));

    const results = await axe.run(document.body, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag22aa"],
      },
      rules: {
        "color-contrast": { enabled: false },
      },
    });
    const severe = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );

    expect(severe, JSON.stringify(severe, null, 2)).toEqual([]);
  });

  it("exposes documented community links and returns focus when dismissed", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Use ChatGPT / Codex" });

    const trigger = screen.getByRole("button", { name: "Open resources menu" });
    await user.click(trigger);
    const resources = screen.getByRole("navigation", { name: "Resources and community" });
    expect(within(resources).getByRole("link", { name: /YouTube/ }).getAttribute("href")).toBe(
      "https://www.youtube.com/@aiathome-adam",
    );
    expect(within(resources).getByRole("link", { name: /GitHub/ }).getAttribute("href")).toBe(
      "https://github.com/AIAtHome-Adam",
    );
    expect(within(resources).getByRole("link", { name: /Troubleshooting/ }).getAttribute("href")).toBe(
      "https://github.com/AIAtHome-Adam/QuotaCompass/blob/main/docs/TROUBLESHOOTING.md",
    );

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("navigation", { name: "Resources and community" })).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("filters the seven-day timeline and labels reset collisions", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Reset horizon" });

    const schedule = screen.getByRole("heading", { name: "Reset horizon" }).closest("section");
    expect(schedule).not.toBeNull();
    expect(within(schedule!).getByText(/2 resets in the next seven days; 1 collision group/)).not.toBeNull();
    expect(within(schedule!).getAllByText("2 resets occur within one hour")).toHaveLength(2);

    const codexFilter = within(schedule!).getByRole("button", { name: "ChatGPT / Codex" });
    await user.click(codexFilter);
    expect(codexFilter.getAttribute("aria-pressed")).toBe("true");
    expect(within(schedule!).getByText("1 reset in the next seven days")).not.toBeNull();
    expect(within(schedule!).queryByText("2 resets occur within one hour")).toBeNull();
  });

  it("marks inferred history resets in both the chart and numeric table", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Use ChatGPT / Codex" });

    const codexCard = screen.getByRole("heading", { name: "ChatGPT / Codex" }).closest("article");
    expect(codexCard).not.toBeNull();
    await user.click(within(codexCard!).getByText("30-day history"));

    expect(await within(codexCard!).findByRole("cell", { name: "Reset inferred" })).not.toBeNull();
    expect(within(codexCard!).getByRole("img", { name: /1 inferred reset boundary/ })).not.toBeNull();
  });

  it("keeps the remote reauth token in memory for one attempt only", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Use ChatGPT / Codex" });

    await user.click(screen.getByRole("button", { name: "Start native login for Cursor" }));
    const token = await screen.findByLabelText("Separate reauthentication token");
    await user.type(token, "reauth-secret");
    await user.click(screen.getByRole("button", { name: "Authorize reauthentication" }));

    await screen.findByText("Cursor login started in the native provider flow.");
    expect(reauthHeaders).toEqual([null, "Bearer reauth-secret"]);
    const sessionValues = Array.from(
      { length: sessionStorage.length },
      (_, index) => sessionStorage.getItem(sessionStorage.key(index) ?? ""),
    ).join("|");
    const localValues = Array.from(
      { length: localStorage.length },
      (_, index) => localStorage.getItem(localStorage.key(index) ?? ""),
    ).join("|");
    expect(sessionValues).not.toContain("reauth-secret");
    expect(localValues).not.toContain("reauth-secret");
    expect(screen.queryByLabelText("Separate reauthentication token")).toBeNull();
  });

  it("keeps dashboard requests same-origin", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "Use ChatGPT / Codex" });

    expect(fetchMock).toHaveBeenCalled();
    for (const [input] of fetchMock.mock.calls) {
      expect(String(input).startsWith("/api/v1/")).toBe(true);
    }
  });

  it("supports keyboard-only theme and manual validation flows", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Use ChatGPT / Codex" });

    const theme = screen.getByRole("button", { name: "Use light theme" });
    theme.focus();
    await user.keyboard("{Enter}");
    expect(document.documentElement.dataset.theme).toBe("light");

    const manualCard = screen.getByRole("heading", { name: "Manual provider" }).closest("article");
    expect(manualCard).not.toBeNull();
    const used = within(manualCard!).getByRole("spinbutton", { name: "Used percentage" });
    used.focus();
    await user.clear(used);
    await user.type(used, "101");
    await user.tab();
    const update = within(manualCard!).getByRole("button", { name: "Update" });
    expect(document.activeElement).toBe(update);
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(within(manualCard!).getByRole("status").textContent).toContain(
        "Enter a percentage from 0 to 100.",
      );
    });
  });
});
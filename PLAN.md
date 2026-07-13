# QuotaCompass — Implementation Plan

**Status:** Plan approved for handoff (rev 9). Execute phases in order; each phase has acceptance criteria. The phases guide the complete build; finish all or nearly all before public release.
**Product name:** **QuotaCompass** (package/CLI `quotacompass`; short alias `qc` suggested). Confirmed free on PyPI, npm, and GitHub (user/org + repo search) on 2026-07-10.
**Repo root:** the checked-out `QuotaCompass` project directory.
**Author context:** Planned 2026-07-10 by Claude (Fable) for execution by Opus 4.8. Rev 2: OpenRouter/Copilot/Gemini/xAI promoted to v1; machine-specifics moved to Appendix A. Rev 3: Phase 1 leads with Claude+Codex; no Hermes dashboard tab; remote reauth = opt-in-with-warning. Rev 4: the Hermes integration ships as a **skill**, not a plugin. Rev 5: skill scope widened to **Hermes + OpenClaw** — one shared skill body, per-target frontmatter, published to both registries (Hermes Skills Hub + ClawHub). Rev 6 (robustness pass): timestamp discipline, platform config/state dirs, CLI↔server coordination, `doctor` command, `--demo` mode, history retention, Phase-0 name/license check. Rev 7: harvested concrete lessons from the incumbent `mm7894215/TokenTracker` (see **Appendix B**) — verified provider endpoints/credential paths now seed the spikes; a hard **zero-telemetry / no-cloud** stance is now an explicit non-goal and a positioning pillar; the name collision forces a rename. Rev 8: name chosen — **QuotaCompass** (a needle that points your agent at the best provider; picked partly for its visual/logo strength for the planned content series), confirmed available on PyPI/npm/GitHub; product/CLI/config namespace renamed from the working title `tokentracker` → `quotacompass` throughout. Rev 9: corrected the repo path; added zero-third-party-runtime, richer state/provenance, adapter maturity, reauth hardening, early advisor/UI slice, and testable accessibility requirements.

---

## 1. What this is

A self-hosted usage-quota tracker for AI subscriptions and APIs. Many providers (Claude Pro, ChatGPT Plus/Codex, Cursor, OpenCode Go, Nous Portal) don't publish absolute token counts, but they DO expose **usage percentage + reset time** per limit window (5h, weekly, monthly). QuotaCompass normalizes those into one model and surfaces it five ways:

1. **State snapshot files** (JSON + Markdown) — the primary agent-facing interface; any agent/cron can read them with zero dependencies.
2. **CLI** (`quotacompass status`, `quotacompass suggest`) — on-demand queries, `--json` for agents.
3. **Self-hosted web dashboard** — human-facing visual view (install option 1).
4. **Agent skills for Hermes and OpenClaw** (install option 2, optional) — `SKILL.md` packages (one shared body, per-target frontmatter) published to the Hermes Skills Hub and ClawHub that teach the agent to query QuotaCompass (CLI → REST → state file), interpret the results, and run scheduled "pre-reset nudge" checks. Users who want the visual view run the standalone dashboard (option 1) alongside; the lanes are independent and complementary.
5. **REST API** — for everything else.

Plus: **auth-token expiry detection** with one-click/scripted re-authentication helpers, and an **advisor** that recommends which provider an agent should use right now to balance quotas ("use-it-or-lose-it" logic).

### Non-goals
- Not an LLM proxy/router — it advises; it never sits in the request path.
- Not a billing/accounting tool — cost reporting is a bonus where an official API exists (Anthropic Admin API, OpenRouter credits), not a core feature.
- Never stores provider credentials in its own DB — it reads native credential stores (Claude Code, Codex CLI, Cursor, opencode, gh/Copilot, gemini-cli, Hermes) **at poll time, in place**.
- **No telemetry, no phone-home, no cloud, no leaderboard — ever, and not as an opt-out.** Nothing leaves the machine except the provider polls the user configured. This is a deliberate, load-bearing difference from the incumbent (which ships a daily analytics heartbeat *on by default* plus an opt-in cloud leaderboard). There is no analytics SDK in the dependency tree; a test asserts the process opens no network connection to any host outside the configured provider set. See Appendix B.
- **No third-party dashboard runtime dependencies.** The dashboard serves every script, stylesheet, icon, font, image, and other asset locally—no Google Fonts, CDN, remote favicon, analytics/error-reporting SDK, or runtime loader. Internet loss can prevent fresh provider polls, but the full UI remains usable with last-known-good state/history and honest freshness labels.

---

## 2. Portability rule (read before coding)

QuotaCompass is a **public, general-purpose tool**. Nothing in the codebase may assume any particular machine, port-numbering scheme, documentation habit, service-naming convention, or WSL topology. Concretely:

- All environment discovery is **auto-detection with config override**: credential-store paths are probed from a list of well-known per-OS locations; free ports are found by live listener scan; WSL is detected, not assumed.
- No hardcoded reserved-port lists, hostnames, IPs, usernames, or file paths outside of (a) documented well-known provider credential locations and (b) `config.example.yaml` placeholders.
- The first deployment target (the author's machine) has specifics — cred paths on both Windows and WSL, an existing port map, existing auth-repair scripts. **All of that lives in Appendix A** and informs *testing*, never *defaults*. If a feature only makes sense on that machine, it belongs in that machine's config file, not in the product.

---

## 3. Architecture

**Language: Python 3.11+** for the core; FastAPI serves the standalone web app. (Python also keeps the door open for a future Hermes *plugin* — Hermes plugins are Python — though v1's Hermes integration is a markdown skill and needs no shared runtime at all; see §8.)

**Frontend: one React + Vite + TypeScript app, one build target** — the standalone dashboard, served by FastAPI static files. (A Hermes dashboard-tab build was considered and deliberately dropped: Hermes doesn't officially document web-UI plugins yet, and the standalone dashboard already covers the visual lane — see §8d.)

```
QuotaCompass/
├── PLAN.md                        # this file
├── pyproject.toml                 # single installable package: quotacompass
├── quotacompass/
│   ├── core/
│   │   ├── models.py              # ProviderStatus, LimitWindow, AuthStatus (pydantic)
│   │   ├── config.py              # load/validate config.yaml
│   │   ├── discovery.py           # credential-store autodetect, WSL detect, port scan
│   │   ├── store.py               # SQLite history (snapshots over time), WAL mode
│   │   ├── statefile.py           # atomic writer: state/current.json + current.md
│   │   ├── advisor.py             # provider suggestion scoring
│   │   └── poller.py              # scheduler loop, per-adapter intervals, jitter, backoff
│   ├── adapters/
│   │   ├── base.py                # Adapter ABC: probe(), fetch_usage(), auth_status(), reauth_hint()
│   │   ├── claude_oauth.py        # Claude Pro/Max via Claude Code creds
│   │   ├── anthropic_api.py       # Anthropic API (Admin usage/cost report or ratelimit headers)
│   │   ├── codex_oauth.py         # ChatGPT Plus via Codex CLI auth.json (multi-store capable)
│   │   ├── cursor.py              # Cursor via app session token
│   │   ├── opencode.py            # OpenCode Go via opencode auth.json
│   │   ├── nous.py                # Nous Portal (portal API or hermes CLI bridge)
│   │   ├── openrouter.py          # OpenRouter — OFFICIAL key/credits endpoints
│   │   ├── copilot.py             # GitHub Copilot quota
│   │   ├── gemini.py              # Google Gemini (API and/or gemini-cli OAuth)
│   │   ├── xai.py                 # xAI / Grok
│   │   └── manual.py              # user-declared providers, % entered via UI/CLI
│   ├── server/
│   │   ├── app.py                 # FastAPI: /api/v1/*, static dashboard, optional token auth
│   │   └── routes.py
│   ├── cli.py                     # `quotacompass` entrypoint
│   └── setup_wizard.py            # onboarding: port scan, adapter autodetect, service install
├── web/                           # React+Vite+TS standalone dashboard
│   ├── src/ ...
│   └── vite.config.ts
├── skills/                        # agent skills (see §8): one shared body, per-target frontmatter
│   ├── shared/
│   │   ├── BODY.md                # single-source procedure/interpretation text
│   │   └── scripts/query.py       # stdlib-only helper (CLI→REST→file resolution ladder)
│   ├── hermes/quotacompass/       # generated: Hermes frontmatter + BODY.md + scripts/
│   │   └── SKILL.md
│   ├── openclaw/quotacompass/     # generated: OpenClaw frontmatter + BODY.md + scripts/
│   │   └── SKILL.md
│   ├── build_skills.py            # tiny assembler: frontmatter template + body → target dirs
│   └── README.md
├── scripts/
│   ├── reauth/                    # per-provider reauth helper scripts (ps1 + sh)
│   └── install-service.{ps1,sh}   # scheduled task (Windows) / systemd user unit (Linux)
├── state/                         # runtime output (gitignored): current.json, current.md
├── config.example.yaml
└── docs/
    ├── AGENTS.md                  # how agents should query QuotaCompass
    ├── PROVIDERS.md               # per-adapter data-source notes + verification log
    └── SECURITY.md
```

One process (`quotacompass serve`) runs poller + API + dashboard. The CLI works without the server running (it can poll on demand or read the last state file).

**Runtime locations (installed vs dev):** config, state, and the SQLite DB default to platform-standard user dirs (via `platformdirs`: `~/.config/quotacompass/` + `~/.local/state/quotacompass/` on Linux, `%APPDATA%\quotacompass\` + `%LOCALAPPDATA%\quotacompass\` on Windows, Library equivalents on macOS), overridable via `--config` / config keys. The repo-local `state/` dir in the tree above is dev-mode only (`quotacompass serve --dev`). The wizard prints the resolved paths — agents and skills need the real state-file location, so `quotacompass paths --json` exposes it programmatically.

**CLI ↔ server coordination:** when a server is already running (detected via a pidfile in the state dir + a port probe), CLI query commands fetch from it instead of polling providers themselves — one poller, one etiquette budget, no double-hitting provider endpoints. `quotacompass status --poll` forces a fresh direct poll only when no server is detected (or with explicit `--force`, warned).

---

## 4. Data model (the normalization contract)

Everything hinges on one normalized shape. Get this right first.

```jsonc
// state/current.json  (schema_version guards future changes)
{
  "schema_version": 1,
  "generated_at": "2026-07-10T14:05:00-06:00",
  "generator": "quotacompass 0.1.0",
  "providers": [
    {
      "id": "claude-pro",                  // stable slug, config-defined
      "label": "Claude Pro (subscription)",
      "kind": "subscription",              // subscription | api | manual
      "support_tier": "stable",             // stable | beta | experimental
      "data_source": "unofficial_api",       // official_api | unofficial_api | local_derived | manual
      "account_hint": "ad…@…(redacted)",   // never full identifiers
      "auth": {
        "status": "ok",                    // ok | expiring_soon | expired | error | unknown
        "expires_at": "2026-07-17T00:00:00Z",  // null if not derivable
        "source": "<credential store path>",
        "reauth": {                        // machine-readable fix instructions
          "command": "claude login",
          "helper_script": "scripts/reauth/claude.ps1",
          "automatable": false
        }
      },
      "windows": [                         // the heart of the model
        {
          "name": "5h",                    // 5h | weekly | monthly | credits | custom
          "used_pct": 34.0,                // 0-100; null if unknown
          "resets_at": "2026-07-10T17:00:00-06:00",
          "resets_in_seconds": 10500,
          "estimated": false               // true when derived/heuristic, not provider-reported
        },
        { "name": "weekly", "used_pct": 61.0, "resets_at": "2026-07-16T23:59:00-06:00", "resets_in_seconds": 554040, "estimated": false }
      ],
      "raw_extras": {},                    // adapter-specific extras (model-level splits, cost, credits)
      "fetched_at": "2026-07-10T14:04:31-06:00",
      "last_success_at": "2026-07-10T14:04:31-06:00",
      "fetch_status": "ok",                // ok | stale | error
      "fetch_error": null,                // otherwise: {code, category, retryable, message, user_action}
      "stale_after": "2026-07-10T14:35:00-06:00"
    }
  ],
  "advisor": {
    "suggestion": "claude-pro",
    "ranking": [
      { "id": "claude-pro", "score": 0.82, "reason": "61% of weekly quota unused; resets in 6d10h" },
      { "id": "codex",      "score": 0.55, "reason": "5h window 78% used; recovers at 17:00" }
    ],
    "expiring_unused": [                   // the "go use your tokens" nudge feed
      { "id": "claude-pro", "window": "weekly", "unused_pct": 39.0, "resets_at": "…", "note": "39% of weekly Claude quota expires Thu 11:59 PM" }
    ]
  }
}
```

`state/current.md` is a human/LLM-friendly rendering of the same data (table + nudges). **Atomic writes** (write temp + rename) so readers never see a torn file. **No secrets ever appear in state files, logs, or the SQLite history** — tokens are read, used for the fetch, and dropped.

**Timestamp discipline (reset times are the entire product — get this rigorously right):** every timestamp is ISO-8601 **with UTC offset**, stored internally as UTC and rendered in the local timezone at display time. Prefer provider-reported epoch/reset timestamps verbatim over any locally computed cadence math; when QuotaCompass must compute a reset itself (manual adapter cadences like `weekly:thu 23:59`), do it with a proper tz library (`zoneinfo`) in the user's configured timezone so DST transitions don't shift resets by an hour. Derived convenience fields (`resets_in_seconds`, `generated_at`-relative values) are correct only at write time — `docs/AGENTS.md` must tell readers to recompute freshness from `resets_at`/`stale_after`, never trust `resets_in_seconds` from an old file. Unit-test a DST-crossing week explicitly.

For API-key providers with credit balances instead of percentage windows (OpenRouter, xAI credits), the adapter maps credits → a `credits` window with `used_pct = spent/limit` where a limit exists, else `used_pct: null` + `raw_extras.credits_remaining`.

Do not overload `used_pct: null`: each window also has `quota_state: metered | unlimited | unknown | unavailable`, a stable `window_id`, and `window_duration_seconds` when known. Advisor results include a component score breakdown and explicit penalty/exclusion reasons so unknown, unlimited, stale, and failed states never collapse into the same meaning.

SQLite (`store.py`) keeps timestamped snapshots per provider/window → the dashboard gets sparklines/burn-rate, and the advisor gets usage velocity. Retention is bounded (`state.history_retention_days`, default 90) with pruning on startup + daily, so the DB never grows unbounded on a long-lived install.

---

## 5. Provider adapters

**Reality check that shapes everything here:** only a few of these have official usage endpoints (Anthropic Admin API, OpenRouter). Subscription adapters ride the same endpoints their own CLIs/apps use, authenticated by the credential files those tools already maintain. That's the same approach as established community tools (ccusage, claude-monitor, cursor-stats), but the endpoints are **unofficial and can change or break**. Therefore:

- `base.Adapter` is a strict contract; breakage in one adapter degrades only that provider card to `fetch_status: error` with the last-good snapshot marked `stale`. Never crash the poller.
- **Phase 1/2 opens each adapter with a research spike** ("verification log" in `docs/PROVIDERS.md`): confirm the endpoint live, record exact request/response, add a recorded-fixture test. **Appendix B has verified endpoints, credential paths, and window-classification gotchas harvested from the incumbent's source** — these turn most spikes from "discover the endpoint" into "confirm it still behaves and record a fixture" (much faster), but still verify each against the live provider; they are unofficial and drift.
- Every adapter needs a **manual fallback**: if fetch breaks, the provider stays visible and the user can type in the % they see in the provider's own UI (with its known reset cadence auto-computing `resets_at`).
- **Credential discovery** (`discovery.py`) probes well-known per-OS paths (Windows/macOS/Linux/WSL-from-Windows) and presents findings for confirmation; config can point at any path, including UNC/WSL paths. Multiple stores for the same product (e.g. two Codex installs) = multiple provider entries.

### Core six (the original requirement)

| Adapter | Credential source (well-known locations) | Usage data path (verify in spike!) | Expiry detection |
|---|---|---|---|
| `claude_oauth` | `~/.claude/.credentials.json` (Linux/Windows, mode 0600); macOS Keychain service `"Claude Code-credentials"` | Verified (Appendix B): `GET https://api.anthropic.com/api/oauth/usage`, headers `Authorization: Bearer <token>` + `anthropic-beta: oauth-2025-04-20`; response carries `five_hour`, `seven_day`, `seven_day_opus`, `weekly_scoped[]` (per-model), `extra_usage`; 401 = expired. Fallback: estimate from `~/.claude/projects/**/*.jsonl` (ccusage approach) with `estimated: true` | `expiresAt` in credentials file; 401 on usage call |
| `anthropic_api` | API key from config/env (`ANTHROPIC_ADMIN_KEY`) | **Official**: Admin API `GET /v1/organizations/usage_report/messages` + `cost_report`. If only a regular key: cheap `count_tokens` request, read `anthropic-ratelimit-*` response headers | API keys don't expire; report `ok`/`unknown` |
| `codex_oauth` | `~/.codex/auth.json` (any number of stores → any number of provider entries) | Verified (Appendix B): `GET https://chatgpt.com/backend-api/wham/usage` (+ `/rate-limit-reset-credits`) with `ChatGPT-Account-Id` header. **Classify windows by `limit_window_seconds` (18000=5h, 604800=weekly), never by slot position** — free tier delivers weekly in the primary slot and position-reading mislabels it. | JWT `exp` decode; `last_refresh`; headless refresh at `auth.openai.com/oauth/token` (Appendix B) |
| `cursor` | `state.vscdb` (SQLite) → `ItemTable` key `cursorAuth/accessToken` (JWT), under the app's `globalStorage` dir (per-OS probe) | Verified (Appendix B): `GET https://cursor.com/api/usage-summary` with cookie `WorkosCursorSessionToken=<userId>%3A%3A<jwt>` and `Referer: https://www.cursor.com/settings`; usage is in **cents** (percent = used/limit cents). | JWT `exp` decode; reauth = "open Cursor and sign in" |
| `opencode` | `~/.local/share/opencode/auth.json` + local `opencode.db` | **Preferred path is auth-free** (Appendix B): sum local USD `cost` from opencode's SQLite `message` table per window ÷ the published OpenCode Go dollar caps ($12/5h, $30/week, $60/month) — dimensionally exact, survives their OAuth churn. Web-scrape of the workspace dashboard is the fragile precise-number fallback; there is **no public quota REST API**. | JWT/refresh fields in auth.json |
|
ous` | Nous Portal token (portal API mode) or a running Hermes install (`bridge` mode: shell out to `hermes portal info` and parse — must match the exact `✓ logged in` marker, since `✗ not logged in` also contains the substring) | **Genuinely novel — the incumbent does not track Nous at all** (Appendix B), so no prior art to lean on; full spike required. Portal API for subscription usage; free-tier/promo models may be uncapped — support a "free/uncapped" display state | Portal token staleness via `hermes portal info` or 401s |

### Common-provider four (promoted to v1 — first thing any other user will ask for)

| Adapter | Credential source | Usage data path (verify in spike!) | Expiry detection |
|---|---|---|---|
| `openrouter` | API key from config/env | **Official**: `GET https://openrouter.ai/api/v1/key` (limit, usage, free-tier flag) and `GET /api/v1/credits` — the easiest adapter and the reference pattern for API-key adapters | keys don't expire |
| `copilot` | GitHub OAuth from `~/.config/github-copilot/apps.json` (or `hosts.json`; per-OS probe) or `gh` CLI token | Verified endpoint (Appendix B): `GET https://api.github.com/copilot_internal/user` exposes plan + premium-request quota; monthly window | OAuth token exchange failure; `gh auth status` |
| `gemini` | gemini-cli OAuth (`~/.gemini/oauth_creds.json`) and/or `GEMINI_API_KEY` | Verified (Appendix B): `https://cloudcode-pa.googleapis.com/v1internal` (Code Assist quota), refresh via `oauth2.googleapis.com/token`; API-key mode may only get ratelimit headers → `estimated`/manual fallback acceptable | OAuth `expiry` field in creds file |
| `xai` | API key from config/env; Grok subscription OAuth where a local store exists | Spike: xAI management/usage API for API credits; Grok subscription limits may be manual-only in v1 | API keys don't expire; OAuth JWT decode where present |

**Extensibility beyond these ten:** the `manual` adapter covers anything immediately; a config-declared `generic_http` adapter (URL + header template + JSONPath extraction) is v1.5 backlog. Document "adding an adapter in ~50 lines" in `docs/PROVIDERS.md`.

**Polling etiquette:** default interval 15 min per adapter (config-overridable), ±10% jitter, exponential backoff on errors, hard floor of 5 min — QuotaCompass must never contribute measurable load or trigger anti-abuse. Poll concurrently under a global concurrency limit with per-adapter hard timeouts and bounded retries honoring `Retry-After`; one slow provider never blocks the cycle. Each adapter exposes its support tier in provider docs, CLI, doctor, API, and dashboard.

---

## 6. Agent-facing interfaces (answering "text file vs CLI")

Do **both** — they're nearly free once the core exists, and they serve different agent situations:

1. **State files** (`state/current.json` + `.md`) — best for crons and non-Hermes agents: zero-dependency read, works even if the server is down (with honest `stale_after` timestamps).
2. **CLI** — `quotacompass status [--json] [--provider claude-pro]`, `quotacompass suggest [--json] [--task agentic|chat|bulk]`, `quotacompass nudges [--json]` (the expiring-unused feed), `quotacompass set` (manual entries), `quotacompass reauth <id>`, `quotacompass paths [--json]`, and `quotacompass doctor [--json]` — a self-diagnostic that checks, with a pass/fail line and a concrete fix hint each: config validity, credential-store reachability per provider, a live probe per adapter endpoint, server/service liveness, port status, and state-file freshness. `doctor` is the first thing README troubleshooting says to run, and the wizard runs it as its smoke test — for a tool built on unofficial endpoints, fast self-diagnosis is what keeps breakage actionable instead of fatal. Exit codes: 0 ok, 3 some-providers-stale, 4 auth-expired-somewhere — so shell crons can branch without parsing.
3. **REST** — `GET /api/v1/status`, `/api/v1/suggest`, `/api/v1/nudges`, `/api/v1/providers/{id}/history?window=weekly&days=30`, `POST /api/v1/providers/{id}/manual`, `POST /api/v1/providers/{id}/reauth` (gated, see §9). Optional static bearer token via config for non-loopback binds.
4. **Hermes skill** (§8) — teaches Hermes to use interfaces 1–3 correctly (resolution ladder: CLI → REST → state file) and ships the scheduled nudge check as a blueprint, so Hermes needs no bespoke integration code at all.

Write `docs/AGENTS.md` as a paste-able instruction sheet for agents: where the file is, what the fields mean, sample cron prompts ("check nudges; if any window >30% unused with <12h to reset, remind me").

---

## 7. Web dashboard (install option 1)

Single-page React app served by the FastAPI process. Design targets:

- **Overview grid**: one card per provider — ring/bar per limit window showing used %, countdown to reset, auth status chip (green/amber/red), staleness indicator. The primary view answers "what should I burn tokens on tonight?" at a glance.
- **Timeline strip**: horizontal time axis (next 7 days) with markers for every upcoming reset — makes staggered-reset planning obvious.
- **Nudge panel**: the `expiring_unused` feed with plain-language lines.
- **History view**: per-provider sparkline of used % over the window (from SQLite) — shows burn rate and whether you'll cap out before reset.
- **Advisor widget**: current ranked suggestion with reasons.
- **Auth panel**: token expiries sorted soonest-first, each with its reauth action (§9).
- **Manual entry inline**: providers in manual/fallback mode get an edit control right on their card (updates `POST /providers/{id}/manual`) — keeping a half-broken provider usable must cost two clicks, not a config edit.
- Dark/light theme; mobile-friendly (phone access over VPN/tailnet is a primary use).
- Decision-first hierarchy: recommendation and expiring-unused actions precede provider telemetry. Cards emphasize the constraining window; secondary windows use compact rows with exact values and reset text always visible.
- Never communicate status by color alone: combine icon, label, and recovery text. Desktop reset timelines group collisions and include filters plus a chronological list; mobile uses a vertical agenda. History charts mark reset boundaries and have keyboard-accessible values plus table/list alternatives.

Keep the stack boring: React + Vite + TS, fetch polling every 60s (no websockets in v1), recharts or hand-rolled SVG for sparklines. Bundle all production assets, including SVG icons and any WOFF2 fonts, in the Python package; use semantic tokens, tabular numerals, restrained motion with prefers-reduced-motion, a restrictive same-origin CSP, and a browser test that fails on any non-self asset request.

**Demo mode:** `quotacompass serve --demo` runs the full server + dashboard against bundled synthetic data (several providers, varied windows, one expiring-unused nudge, one expired auth, one stale fetch). This unblocks dashboard development, produces safe screenshots with no personal data, and lets a prospective user evaluate the complete UI without credentials. Demo mode covers metered, unlimited, unknown, manual, stale, error, expired-auth, expiring-unused, long-label, and large-provider-count states; it is an evaluation/privacy feature, not a reason to release before the planned phases are complete.

---

## 8. Agent-skill integrations: Hermes + OpenClaw (install option 2)

**Authoritative references (read all before Phase 5):**
- Hermes — creating skills: https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills · decision framework: https://hermes-agent.nousresearch.com/docs/developer-guide/adding-tools
- OpenClaw — skills: https://docs.openclaw.ai/tools/skills (follows the AgentSkills spec: https://agentskills.io)
- Hermes plugins (backlog option only): https://hermes-agent.nousresearch.com/docs/developer-guide/plugins · https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins

### 8a. Why skills are the right tool

Hermes's own docs define the decision boundary: a **skill** is for capabilities expressible as "instructions + shell commands + existing tools", especially anything that "wraps an external CLI callable via terminal" without custom Python integration; **tools/plugins** are for custom API integration, binary data, or streaming. QuotaCompass's integration is exactly the former — the plugin design we previously sketched had handlers that were nothing but thin HTTP/file reads around the `quotacompass` CLI and REST API. Per the framework, that should be a skill. Skills also run **zero code inside the agent process** (no interference risk), and get first-class official distribution on both platforms: Hermes Skills Hub (`hermes skills publish … --to github`, `hermes skills browse/install`, security scanning, trust levels) and OpenClaw's ClawHub (`openclaw skills install @owner/quotacompass`, trust envelopes via `openclaw skills verify`).

And because both platforms are SKILL.md-based (OpenClaw explicitly follows the AgentSkills spec; Hermes's format is a close cousin), **one skill body serves both** — only the frontmatter differs. A tiny `build_skills.py` assembler stitches per-target frontmatter templates onto the shared `BODY.md` + `scripts/`; the body text and the `query.py` resolution ladder are written once. This also leaves the door open to further AgentSkills-spec targets later at near-zero cost.

### 8b. Shared body + Hermes packaging (`skills/hermes/quotacompass/`)

Hermes `SKILL.md` frontmatter per the official schema, plus the shared stdlib-only helper script:

```yaml
---
name: quotacompass
description: Check AI subscription/API quota usage, reset times, provider suggestions, and auth health via QuotaCompass
version: 0.1.0
author: …
metadata:
  hermes:
    tags: [Productivity, DevOps]
    requires_toolsets: [terminal]
    config:
      - key: quotacompass.url
        description: "Base URL of a running QuotaCompass server"
        default: "http://127.0.0.1:4747"
      - key: quotacompass.state_file
        description: "Path to state/current.json for file-mode fallback (blank = disabled)"
        default: ""
    blueprint:
      schedule: "0 20 * * 4"     # example: Thursday evening pre-reset check
      prompt: "Run the quotacompass skill's nudge check; if any quota window is >25% unused and resets within 24h, remind me which provider to use tonight."
---
```

Body sections (per official conventions — "When to Use", "Procedure", "Pitfalls", "Verification") teach the agent to:

1. **Query** with a resolution ladder: local `quotacompass status --json` CLI if installed → `curl <quotacompass.url>/api/v1/status` (bearer token from env if set) → read `quotacompass.state_file` directly (noting `stale_after`). A small `scripts/query.py` helper (invoked as `python3 ${HERMES_SKILL_DIR}/scripts/query.py status`) encapsulates that ladder so the instructions stay short and deterministic.
2. **Interpret** the schema: what `windows[].used_pct`/`resets_at`/`estimated` mean, how to read `advisor.ranking` reasons and the `expiring_unused` nudge feed, and to surface the standalone dashboard URL when the user wants the visual view.
3. **Act**: answer "how are my tokens?", pick a provider for a task via `/api/v1/suggest`, run the nudge check (the blueprint automates this on a schedule — this *is* the "remind me to use my tokens before reset" cron, shipped as a product feature), and — where reauth is permitted (§9) — run `quotacompass reauth <id>` locally or POST the reauth endpoint, quoting the risk warning the first time.

This covers everything the plugin design offered at the same functional level: model-invoked queries mid-conversation (skills activate on relevant requests), scheduled nudges (blueprint > hand-rolled cron), and agent-driven reauth. The only real losses on Hermes are a registered `/tokens` slash command and schema-enforced tool calls — cosmetic here, since the underlying CLI/REST contract is machine-precise anyway (and OpenClaw's packaging restores the slash command on that platform, see 8c).

### 8c. OpenClaw packaging (`skills/openclaw/quotacompass/`)

Same `BODY.md` + `scripts/query.py`, with AgentSkills-spec frontmatter and OpenClaw's gating/config conventions:

```markdown
---
name: quotacompass
description: Check AI subscription/API quota usage, reset times, provider suggestions, and auth health via QuotaCompass
homepage: <repo URL>
user-invocable: true          # gives OpenClaw users a /quotacompass slash command
metadata:
  {
    "openclaw": {
      "requires": { "anyBins": ["quotacompass", "curl", "python3"] },
      "os": ["darwin", "linux", "win32"]
    }
  }
---
```

- Config: server URL / state-file path via OpenClaw's per-skill config bag (`skills.entries.quotacompass.config`) with env-var fallback, mirroring the Hermes `quotacompass.*` config keys so `docs/AGENTS.md` documents one mental model.
- Gating: `requires.anyBins` keeps the skill hidden on hosts with no way to query QuotaCompass at all.
- Scheduled nudges: OpenClaw has no blueprint equivalent in the skill format — document the one-line cron/scheduled-job setup in the skill body instead ("ask your agent to schedule the nudge check daily").
- Distribution: publish to **ClawHub** (`openclaw skills install @<owner>/quotacompass`; `--global` for the managed dir), plus plain git/local installs. Verify field details against docs.openclaw.ai at build time — the plan's snippet is from the July 2026 docs.

### 8d. Plugin: backlog only, with a concrete trigger

Build a plugin later **only if** a need appears that the docs' own framework assigns to tools/plugins — e.g. streaming quota updates into Hermes, or if skill-based terminal access proves too indirect in practice. Same for a dashboard tab: only if/when Nous officially documents web-UI plugins. Both inherit this plan's REST API unchanged, so deferring costs nothing architecturally. (Publishing to the Skills Hub already fulfills the "publish something official for Hermes" goal — and at a higher trust tier than third-party plugin code, since skills are scanned markdown, not arbitrary Python.)

---

## 9. Auth lifecycle & re-authentication

Three tiers, increasing automation, user opts in per provider:

1. **Detect & display (v1, all providers):** every adapter reports `auth.status` + `expires_at` (JWT `exp` decode where tokens are JWTs; file mtime + provider 401s as weaker signals). Dashboard auth panel + CLI exit code 4 + a nudge line ("Codex token expires in 2 days").
2. **Guided reauth (v1):** each provider has a helper script (`scripts/reauth/<id>.ps1|.sh`) that launches the provider's own flow: `claude login`, `codex login`, `opencode auth login`, "open Cursor → sign in", `gh auth login`, provider portal URLs. Dashboard button + `quotacompass reauth <id>` run the helper. **Gating — warn, don't block:** reauth helpers execute local commands, so the trigger is tiered: `security.reauth_trigger: local` (default — REST/UI trigger on loopback only; remote UIs show the command to run instead of a button) or `remote` (trigger allowed from LAN/Tailscale/agents). Setting `remote` requires `server.auth_token` to be set, and both the setup wizard and the dashboard display a clear warning of what it means (any client holding the token can execute the configured reauth commands on this machine). Separate read and reauth token scopes; never persist reauth capability in browser local storage. Remote requests accept only a provider ID mapped to a fixed installed helper, reject symlink/unsafe helper targets where the OS exposes that information, are rate-limited with per-provider cooldowns, and create secret-free audit events. Never expose raw subprocess environment or unredacted output. Agent-driven reauth is a first-class supported use case, not a discouraged one — the Hermes skill's reauth procedure (§8b) rides this same setting (or simply runs the CLI via terminal when co-located, which needs no remote exposure at all).
3. **Hands-off refresh (v1.5, opt-in per provider):** for providers where a refresh-token flow works headlessly, a `--fix` mode refreshes without interaction. The **Codex path is proven** (Appendix B): `POST https://auth.openai.com/oauth/token` with the public client id, refresh when `last_refresh` > ~8 days, persist with an **atomic 0600 write** so a mid-write kill can't corrupt `auth.json` and force a full re-login. Design rule: **read-only checks by default; mutation only under an explicit `--fix` flag**, and when a flow needs a human step (email confirmation, CAPTCHA), report "manual step required" — never silently fail. Hooks for browser-assisted refresh (driving a local CDP Chrome) are exposed as an extension point, not core behavior.

**Security file (`docs/SECURITY.md`) must state:** credentials are read in place from native stores and never copied/persisted; any credential the tool *does* rewrite (headless token refresh) uses an atomic `0600` write; state files and logs are secret-free; server binds `127.0.0.1` by default; non-loopback bind requires the bearer token; the reauth trigger defaults to loopback-only and remote triggering is an explicit, warned opt-in; the SQLite DB contains only percentages and timestamps; **no telemetry or network egress to any non-provider host, with no opt-out needed because it does not exist.** Adopt the incumbent's good hygiene (private vulnerability disclosure channel, an explicit "counts and timestamps only" rule treated as a security invariant) — see Appendix B for what to copy vs. deliberately reject.

---

## 10. Advisor ("which provider should the agent use right now")

Deterministic, explainable scoring — no ML, reasons always included:

```
score(provider) =
    w_headroom  * min over windows of (1 - used_pct/100)      # tightest window dominates
  + w_urgency   * urgency_bonus                               # unused quota near reset = "use it or lose it"
  + w_recovery  * short_window_recovery                       # a 5h window that resets soon barely counts against
  - w_health    * penalties (auth expired/error, stale data)
  + w_priority  * user preference weight from config
```

- `urgency_bonus` grows as `resets_at` approaches while `used_pct` is low — this formalizes the common human pattern of scheduling heavy work into a "pre-reset lane" just before a weekly quota rolls over.
- Optional `--task` hint maps to per-provider capability weights in config (e.g. `agentic: {claude-pro: 1.0, codex: 0.9}`) — config-driven, no hardcoded opinions.
- Providers can be marked `linked_account: <group>` in config so two credential stores for one underlying account (e.g. two Codex installs) don't double-count in rankings/nudges.
- Outputs: top suggestion + full ranking + human-readable reason strings, in state file, CLI, and REST (and thus to the skills, which just read those).
- `advisor.nudge_threshold` config: what counts as "expiring unused" (default: >25% unused with <24h to reset).
- v1 keeps weights static in config; burn-rate-aware projections ("at current velocity you'll cap out 9h before reset") come in v1.5 using SQLite history.

---

## 11. Onboarding wizard (`quotacompass setup`)

Interactive first-run flow (also `--non-interactive` with flags for agent-driven installs). Everything below is generic auto-detection — no assumptions about the host:

1. **Port selection:** enumerate live listeners cross-platform (`psutil.net_connections()`); on Windows with WSL present, also enumerate WSL-side listeners (they may be reachable/forwarded on Windows-visible ports). Propose the first free port from a candidate list (default `4747`, incrementing). Show *what was detected* ("ports in use right now: 3000, 3001, 9119, …") and let the user confirm or override. An optional `reserved_ports` config key lets users who maintain their own port plans pre-block ports that aren't currently listening; it starts empty.
2. **Adapter autodetect:** probe well-known credential paths for all ten adapters across native OS paths and (when detected) WSL distro paths; show findings ("Claude Code creds ✓ · Codex ✓ ·  Codex (WSL:Ubuntu) ✓ · Cursor ✓ · gh/Copilot ✓ · …"); user confirms/edits; write `config.yaml`.
3. **First poll + smoke test:** run `quotacompass doctor` (§6) — adapters polled once, results table shown, failures marked with their fallback options and fix hints.
4. **Service install (optional):** Windows → logon Scheduled Task (`QuotaCompass`); Linux/WSL/macOS → systemd user unit / launchd plist. Print the resulting URLs.
5. **Integrations (optional):** if a Hermes install is detected (`~/.hermes/` exists), print the skill install command (`hermes skills install <owner/repo>` once published, or the local-path install for development) and its config keys (`quotacompass.url`, optional `quotacompass.state_file`); if an OpenClaw install is detected (`~/.openclaw/` exists), print `openclaw skills install @<owner>/quotacompass` and the `skills.entries.quotacompass.config` keys; offer to copy the sample cron prompt from `docs/AGENTS.md` for other agents.
6. Final screen: where the state file lives, how agents should query it, and a reminder that if the user documents their ports somewhere, they may want to record the new one (QuotaCompass doesn't know or care where).

---

## 12. Config (`config.example.yaml`)

```yaml
server:
  host: 127.0.0.1          # 0.0.0.0 requires auth_token
  port: 4747
  auth_token: null
security:
  reauth_trigger: local        # local (loopback-only, default) | remote (LAN/VPN/agents;
                               # requires server.auth_token; wizard + UI warn about the risk) | off
poll:
  default_interval_minutes: 15
state:
  dir: null                    # null = platform default (see §3 runtime locations); set for dev mode
  history_retention_days: 90
reserved_ports: []             # optional: ports to avoid even if not currently listening
providers:
  claude-pro:
    adapter: claude_oauth
    credentials: "~/.claude/.credentials.json"   # autodetected by setup
    priority: 1.0
  codex:
    adapter: codex_oauth
    credentials: "~/.codex/auth.json"
  cursor:
    adapter: cursor
    state_db: "<autodetected per-OS globalStorage path>/state.vscdb"
  opencode:
    adapter: opencode
    credentials: "~/.local/share/opencode/auth.json"
  nous:
    adapter: nous
    mode: portal_api           # or: hermes_bridge
  anthropic-api:
    adapter: anthropic_api
    admin_key_env: ANTHROPIC_ADMIN_KEY
  openrouter:
    adapter: openrouter
    api_key_env: OPENROUTER_API_KEY
  copilot:
    adapter: copilot
    credentials: "~/.config/github-copilot/apps.json"
  gemini:
    adapter: gemini
    credentials: "~/.gemini/oauth_creds.json"    # and/or api_key_env: GEMINI_API_KEY
  xai:
    adapter: xai
    api_key_env: XAI_API_KEY
advisor:
  nudge_threshold: { unused_pct: 25, within_hours: 24 }
  task_weights:
    agentic: { claude-pro: 1.0, codex: 0.9 }
```

(A machine-specific overlay for the first deployment — dual Codex stores via WSL UNC paths, `linked_account` grouping, hermes_bridge mode — is sketched in Appendix A, not shipped as defaults.)

---

## 13. Execution phases (with acceptance criteria)

**Phase 0 — Scaffold (small)**
Name is settled: **QuotaCompass**, package/CLI `quotacompass` (short alias `qc` suggested) — confirmed free on PyPI, npm, and GitHub (user/org + repo search, 2026-07-10), deliberately distinct from the incumbent's taken `tokentracker`/`tokentracker-cli` (Appendix B). The on-disk repo folder is `QuotaCompass/`; every shipped identifier uses `quotacompass`. Choose a license (MIT unless the author objects). Then: repo layout, pyproject (package name `quotacompass`, console-script `quotacompass`), pydantic models, config loader + platform-dirs resolution (§3), discovery module skeleton, empty adapter ABC, pytest harness, and a minimal CI matrix (GitHub Actions: ubuntu + windows + macos, lint + tests) so cross-platform breakage surfaces per-commit instead of at release. ✅ `pip install -e .` works; `quotacompass --help` runs; CI green on all three OSes.

**Phase 1 — Core loop + first adapters (Claude, Codex)**
Lead with the providers the first real user exercises daily, so every result is verifiable against ground truth (the providers' own UIs) from day one. Research spikes + implementation for Claude and Codex (verification log in `docs/PROVIDERS.md`, recorded fixtures). Poller, SQLite store, state-file writer, `status` CLI. Add a minimal deterministic advisor (headroom, reset urgency, health, and user priority, with score breakdown/reason) and a demo-backed UI vertical slice; later phases deepen rather than introduce the product thesis. ✅ `quotacompass status --json` shows live Claude + Codex data with real percentages and reset times that match what their own UIs display; state files update atomically on an interval; secrets never appear in output (grep-audited).

**Phase 2 — Remaining adapters + auth lifecycle**
OpenRouter first within this phase (official API, no spike risk — establishes the reference pattern for API-key adapters), then Cursor, opencode, Nous, anthropic_api, Copilot, Gemini, xAI, manual. JWT expiry decode, `auth.status` everywhere, reauth helper scripts (tier 2), `reauth` CLI. Spike-fails ship as manual-fallback + auth-detection-only rather than stalling the phase. ✅ every configured provider renders a card's worth of data or an honest error+fallback; an expired token flips status within one poll cycle.

**Phase 3 — REST API + web dashboard**
FastAPI routes, `--demo` mode (build it first — it decouples UI work from adapter availability), React dashboard (overview grid, timeline strip, nudges, auth panel, inline manual entry, history sparklines). ✅ a first-time user identifies the recommended provider and next expiring quota in <10 seconds; all demo states render at 375/768/1024/1440px without clipping or unintended horizontal scrolling; core flows are keyboard-completable; automated WCAG 2.2 AA checks have no serious/critical violations; charts have numeric summaries and accessible alternatives; background refresh preserves data/layout; both themes pass contrast checks; production assets render with external requests blocked.

**Phase 4 — Onboarding wizard + service install + doctor**
Port scan, adapter autodetect, non-interactive mode, `quotacompass doctor`, scheduled task/systemd/launchd install. ✅ fresh-machine dry run: `pipx install` → `quotacompass setup` → working dashboard on an auto-suggested free port with zero manual config edits; `doctor` correctly diagnoses at least: missing cred file, dead endpoint, stopped service, stale state.

**Phase 5 — Agent skills (Hermes + OpenClaw)**
Re-read both skills docs; write `BODY.md` + `scripts/query.py` + per-target frontmatter templates + `build_skills.py`; test locally on both (`hermes chat --toolsets skills -q "…"`; OpenClaw workspace-skill install + `/quotacompass`); publish to the Hermes Skills Hub and ClawHub. ✅ both agents answer "how are my tokens looking?" correctly through the skill; the Hermes blueprint nudge check produces a correct pre-reset reminder; `/quotacompass` works in OpenClaw; a stranger can install from either registry; zero code runs inside either agent process.

**Phase 6 — Advisor + agent docs + polish**
Scoring, `suggest`/
udges`, `linked_account` dedupe, `docs/AGENTS.md` with sample cron prompt, `SECURITY.md`, README with both install options. ✅ the skill blueprint (or an AGENTS.md-derived cron on any other agent) correctly produces a "use your Claude tokens before the weekly reset" reminder against real data.

**v1.5 backlog (do not build in v1):** hands-off token refresh (tier 3), burn-rate projections, `generic_http` adapter, push notifications (ntfy/Discord webhook), websocket live updates, multi-machine aggregation (a second box reporting into one server), additional AgentSkills-spec skill targets, Hermes plugin and/or dashboard tab (only on the concrete triggers in §8d).

---

## 14. Risks & honest caveats

1. **Unofficial endpoints WILL eventually break.** Mitigated by: adapter isolation, stale-not-crash behavior, manual fallback per provider, fixtures that make breakage obvious in tests, and `docs/PROVIDERS.md` as a living verification log.
2. **ToS gray zone:** subscription adapters use the user's own OAuth tokens against endpoints the vendor's own tools call, at gentle poll rates, for personal use — same posture as ccusage/claude-monitor/cursor-stats. Keep poll rates low; document this posture in the README so users understand what they're opting into.
3. **Spike-heavy Phase 2:** Copilot/Gemini/xAI usage surfaces are the least certain of the ten. The phase explicitly allows shipping any of them as manual-fallback + auth-detection-only; don't let one provider stall the release.
4. **Multiple stores / one account:** two credential stores may share one account server-side, so their usage windows mirror each other while auth expiry differs per store. `linked_account` config keeps advisor/nudges honest.
5. **Remote reauth is a real attack surface when enabled.** `security.reauth_trigger: remote` means a bearer token authorizes executing the configured reauth commands. Mitigations: off-by-default, requires auth token, helpers are fixed scripts from `scripts/reauth/` (never arbitrary commands from the request), and the wizard/UI warn explicitly at enable time.
6. **Cursor token extraction** may be the most brittle (Electron storage changes, possible encryption). If the spike fails, ship Cursor with manual fallback + auth detection only.
7. **WSL paths from Windows** (`\\wsl.localhost\...`) require the distro to be running. Adapters must treat unreachable-cred-store as `fetch_status: error` with last-good data retained.

## 15. Reference material for the implementer

- **Hermes docs (authoritative):** creating skills https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills · skill-vs-tool-vs-plugin framework https://hermes-agent.nousresearch.com/docs/developer-guide/adding-tools · plugins (backlog option) https://hermes-agent.nousresearch.com/docs/developer-guide/plugins · https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- **OpenClaw docs (authoritative):** skills https://docs.openclaw.ai/tools/skills · AgentSkills spec https://agentskills.io
- Skill structure examples: the bundled `skills/` and `optional-skills/` trees in any Hermes install; OpenClaw bundled skills in any OpenClaw install; dashboard-tab de-facto reference if §8d ever triggers: bundled `hermes-achievements` plugin (upstream `github.com/PCinkusz/hermes-achievements`).
- Community prior art for adapter details: `ccusage` (Claude JSONL parsing), Claude usage-monitor projects (OAuth usage endpoint), `codex` CLI source (rate-limit surface), cursor-stats-style extensions (Cursor session token + usage API), opencode source (auth.json format), gemini-cli source (OAuth quota surface), OpenRouter API docs (`/api/v1/key`, `/api/v1/credits`).

---

## Appendix A — First-deployment acceptance profile (NOT product defaults)

The first acceptance environment is a Windows 11 workstation with WSL2 and multiple local agents. Exact usernames, addresses, occupied ports, service names, and private filesystem locations are deliberately excluded from this public plan. None of these details may become shipped defaults.

- **Credential stores on both sides:** exercise discovery across Windows and WSL, including two Codex credential stores. Use `linked_account` only after confirming that the stores share server-side quota.
- **Port selection:** test automatic selection against a realistic occupied-port list. The chosen port must remain configurable and loopback-only by default.
- **Hermes and OpenClaw:** run both agents from WSL against one Windows-hosted QuotaCompass instance through the WSL gateway. Verify that both receive consistent advice for shared subscriptions.
- **Skill installation:** test local development installs using each agent's documented skill directory before registry publication; do not embed host-specific paths in the skill.
- **Nous adapter:** exercise `hermes_bridge` mode and the tier-3 reauth extension point with a user-configured helper command. Browser-assisted helpers remain opt-in and must never ship with private addresses.
- **Unmetered capacity:** exercise the uncapped display state when a provider temporarily omits a normal quota window.
- **Advisor ground truth:** verify that the urgency model naturally identifies useful pre-reset work windows from quota data rather than hard-coded schedules.
- **Local operations:** document listeners and startup services in the operator's own inventory. The product wizard remains generic (§11 step 6).

---
## Appendix B — Lessons harvested from the incumbent (`mm7894215/TokenTracker`)

Reviewed at v0.75.1 (2026-07-10, MIT, ~970★, Node.js). It is a mature **retrospective consumption tracker** across 25 coding tools (hooks + plugins + passive SQLite/JSONL readers, a LiteLLM cost engine, native menu-bar/tray apps). We are building a **prospective quota advisor** — a different thesis — so this is a source of worn paths, not a competitor to clone. Confidence note: the items below were read from its source on the review date; endpoints are unofficial and drift — every one still gets a live-verify + recorded fixture in its spike.

### B1. Verified provider endpoints & credential handling (accelerates the spikes)

- **Claude** — creds: macOS Keychain service `"Claude Code-credentials"`; Linux/Windows `~/.claude/.credentials.json` (mode `0600`). Usage: `GET https://api.anthropic.com/api/oauth/usage`, headers `Authorization: Bearer <access_token>` + `anthropic-beta: oauth-2025-04-20`. Response keys: `five_hour`, `seven_day`, `seven_day_opus`, `weekly_scoped[]` (per-model, `kind: "weekly_scoped"` + `scope.model.display_name` + `utilization` + `resets_at`), `extra_usage`. `401` ⇒ expired. Retries on `429/503` honoring `Retry-After`.
- **Codex** — usage: `GET https://chatgpt.com/backend-api/wham/usage` and `.../wham/rate-limit-reset-credits`, header `ChatGPT-Account-Id: <accountId>`. **Window classification gotcha (important):** classify by `limit_window_seconds` — `18000`=5h session, `604800`=weekly — **not** by `primary/secondary` slot position, because free-tier accounts deliver the weekly window in the primary slot and position-reading mislabels it "5h". (This normalization is credited to `steipete/CodexBar`.)
- **Codex token refresh (proven headless path for tier-3):** `POST https://auth.openai.com/oauth/token`, JSON body `{ client_id: "app_EMoamEEZ73f0CkXaXp7hrann" (public), grant_type: "refresh_token", refresh_token, scope: "openid profile email" }`. Refresh when `last_refresh` older than ~8 days. `401` ⇒ refresh token revoked → tell user to run `codex`. Persist via **atomic write to a temp file then rename, mode `0600`** so a mid-write kill can't corrupt `auth.json`.
- **Cursor** — token: `state.vscdb` SQLite → `ItemTable` key `cursorAuth/accessToken` (a JWT). Usage: `GET https://cursor.com/api/usage-summary` with `Cookie: WorkosCursorSessionToken=<userId>%3A%3A<jwt>` and `Referer: https://www.cursor.com/settings`. Values are in **cents**; percent = used_cents / limit_cents. (CSV export endpoint also exists for detail.)
- **OpenCode Go** — **the accurate path is auth-free and local:** sum USD `cost` from opencode's `opencode.db` SQLite `message` table per window ÷ the published dollar caps (`$12`/5h, `$30`/week, `$60`/month — opencode.ai/docs/go). This is dimensionally exact and survives their OAuth churn. The precise-but-fragile alternative is scraping `https://opencode.ai/workspace/<id>/go` with an `auth=` cookie (breaks often since auth moved to `auth.opencode.ai`). There is **no public quota REST API**, and the `sk-` API key authenticates only inference, not usage. Parse the scrape anchor-free (their SSR wrapper shape changes between releases).
- **Copilot** — `GET https://api.github.com/copilot_internal/user` (plan + premium-request quota; monthly window). Creds via `~/.config/github-copilot/apps.json` / `hosts.json` or `gh` token.
- **Gemini** — Code Assist quota at `https://cloudcode-pa.googleapis.com/v1internal`; OAuth refresh via `https://oauth2.googleapis.com/token`; creds `~/.gemini/oauth_creds.json`.
- **Others present** (for the optional/backlog set): Grok `https://cli-chat-proxy.grok.com`; Kimi `https://api.kimi.com/coding/v1/usages` (+ `auth.kimi.com/api/oauth/token`); z.ai / ZCode `https://zcode.z.ai/api/v1/zcode-plan`.
- **Not covered by the incumbent at all:** **Nous Research, OpenRouter, xAI/Grok API credits, Anthropic Admin API.** These are pure-novel for us (no worn path to borrow — full spikes), and the Nous + agent-quota angle is the heart of our differentiation and the YouTube story.

### B2. Engineering patterns worth adopting

- **Classify windows by duration, not by field name/position** (the Codex lesson generalizes — any provider that returns positional windows).
- **Atomic `0600` writes** for anything that touches a credential file; never mutate `auth.json` in place.
- **Per-provider fetch timeouts + bounded retries honoring `Retry-After`**, each provider isolated so one hang/failure never blocks the others — matches our "stale-not-crash" rule; confirm our poller does the same.
- **`doctor` as first-class support surface** — their check registry (each check has a stable `id`, a pass/fail, and a hint; groups: runtime config, fs/dir, cli entrypoint, network/base-url) is a good shape for our §6 `doctor`.
- **WSL probe** — parse `wsl.exe -l -v` handling UTF-16LE + BOM + the `*` default-distro marker; cache the distro/user list; expose explicit modes (native-first / wsl-first / both). Good template for our cross-boundary discovery (§11).
- **Dedup on a composite key** so totals reconcile with each provider's own dashboard (their claimed edge over `ccusage`). Less central for us since we read percentages, but if we ever sum JSONL as a Claude fallback, adopt the same discipline.
- **Anchor-free / tolerant parsing** of any HTML/SSR scrape, with fixtures — scrape shapes churn.

### B3. What we deliberately reject (and why — the positioning + the video's side-plot)

- **Telemetry on by default.** The incumbent sends an anonymous daily heartbeat (sha256 machine-id hash, version, platform, shell) to PostHog unless the user sets `TOKENTRACKER_NO_TELEMETRY` / `DO_NOT_TRACK`. Ours has **no telemetry at all** — nothing to opt out of, no analytics dependency in the tree (see §1 non-goals; enforce with a no-egress test).
- **Opt-in cloud leaderboard / cross-device account sync.** We ship **no cloud component**. Quota state is arguably more sensitive than raw token counts (it maps your subscription tier and behavioral patterns), and the trust cost of shipping it to a third-party service maintained by an unknown solo author is not one the user is willing to pay. Local-only, full stop.
- **Breadth-first tool coverage.** Matching 25 tools is their moat, not ours. We cover the user's real set well and lean on the advisor/auth/agent layer for value.
- These three rejections are the honest, concrete answer to "why build your own when this exists?" — a clean narrative beat for the video: *evaluated a capable incumbent, borrowed its hard-won endpoint knowledge, and rejected its cloud/telemetry model to build a private, agent-native advisor.*

### B4. Housekeeping

- The incumbent owns `tokentracker` / `tokentracker-cli` (npm, Homebrew tap, the `tokentracker` binary) — which is exactly why we ship as **QuotaCompass** / `quotacompass` (Phase 0). No PATH or registry collision.
- License is MIT — borrowing API/endpoint *knowledge* (facts, not copied code) is clean; if any snippet is ever adapted directly, honor MIT attribution. Prefer clean-room: read for the endpoint/behavior, implement fresh in Python.
- A local clone was reviewed under the session scratchpad and is disposable; nothing from it is vendored into the repo.

# QuotaCompass

QuotaCompass is a self-hosted AI quota dashboard and advisor. It combines subscription and API usage windows, reset times, authentication health, and freshness into local JSON/Markdown state, a CLI, a REST API, and a bundled web dashboard.

Release status: **v0.1.1 public alpha**. The core state schema is versioned and tested, but provider-owned quota surfaces may evolve between releases.

It has no telemetry, cloud account, leaderboard, Google Fonts, CDN, or third-party runtime asset. Provider polling requires internet access and is constrained to each enabled adapter's explicit HTTPS host allowlist; normalized state and history stay on your machine.

## Install and start

Python 3.11 or newer is required. After the v0.1.1 PyPI publication, install with:

```text
python -m pip install quotacompass
quotacompass setup
quotacompass poll
quotacompass serve
```

To install from source or test a GitHub release before PyPI publication:

```text
git clone https://github.com/AIAtHome-Adam/QuotaCompass.git
cd QuotaCompass
python -m pip install .
quotacompass setup
quotacompass poll
quotacompass serve
```

Open `http://127.0.0.1:4747/`. For screenshots, evaluation, or exploration without personal data, use `quotacompass serve --demo`.

Setup is a dry run unless you approve writing or pass `--write`. It reports native/WSL listener ports, avoids detected and reserved collisions, and prints the proposed dashboard/API/state locations. Automation can use `quotacompass setup --non-interactive --json`; add `--write` only when intended. `quotacompass paths --json` reports platform-standard config/state locations.

## Everyday commands

```text
quotacompass status --json
quotacompass status --poll --json
quotacompass suggest --task agentic --json
quotacompass nudges --json
quotacompass doctor
quotacompass set manual-provider --window weekly --used-pct 35 --cadence "weekly:thu 23:59" --timezone America/Denver
quotacompass reauth claude-pro
```

When the server is running, query and refresh commands use it instead of creating a second poller. `--force` deliberately bypasses that protection and prints a duplicate-request warning.

Status and diagnostic commands exit 4 for expired authentication and 3 for stale/error state, allowing shell automation without parsing prose. Reauthentication launches only packaged fixed helpers; API callers cannot supply commands or paths.

## Providers and fallback

Claude OAuth, Codex OAuth, and manual entries are stable foundations; Cursor is beta. OpenCode, Nous, Anthropic Admin, OpenRouter, Copilot, Gemini, and xAI are experimental because quota surfaces or account prerequisites vary. See `docs/PROVIDERS.md` for provenance and live/fixture verification.

Polling defaults to 15 minutes with jitter, bounded concurrency, hard timeouts, bounded retry, `Retry-After`, and provider isolation. An outage retains honest last-known-good state. Any failed provider can accept a manual percentage and reset/cadence; live data automatically takes precedence again after recovery.

For Codex, QuotaCompass also recognizes the authenticated weekly-only response OpenAI uses during temporary short-window capacity boosts. It reports the 5-hour lane as temporarily unmetered—not permanently unlimited—keeps the weekly cap visible, and gives the opportunity a weekly-headroom-bounded advisor bonus. Missing or malformed fields do not trigger the inference.

## Dashboard security

Loopback is the default. Non-loopback binds require `server.auth_token`. When API authentication is enabled, the dashboard prompts for that read token and keeps it only in the current tab's `sessionStorage`; it is sent solely to the same QuotaCompass origin. Remote reauthentication additionally requires a distinct `security.reauth_token`; the dashboard holds it only in form memory for one attempt and never saves it in browser storage.

## Agent integrations

Generated Hermes and OpenClaw skills live under `skills/`. Both use one shared stdlib-only helper with CLI, then REST, then `current.json` fallback. See `skills/README.md` for local installation/testing. Registry publication is a separate authenticated release action.

When setup detects either agent, it reports the wheel-packaged local skill source, environment-specific development install guidance, future registry command, and URL/state-file config keys. Setup never installs or publishes an agent skill automatically.

For other agents, use `docs/AGENTS.md`, which includes schema interpretation and a pre-reset reminder prompt.

## Services and development

User-service helpers are scripts/install-service.ps1 for Windows and scripts/install-service.sh for systemd/launchd, and both ship in the wheel. Setup reports platform-specific review/install/uninstall commands but never executes them; review uses WhatIf on Windows and a no-write rendered preview on Unix.

```text
python -m pip install -e ".[dev]"
python -m ruff check . --no-cache
python -m pytest -p no:warnings
cd web && pnpm install && pnpm run build
python -m build
```

Run `quotacompass doctor` first when troubleshooting. It checks local prerequisites, service ownership, state freshness, and bounded live adapter access, returning a code and repair hint for each failure.

The dashboard resource menu links to getting started, the local API reference, [troubleshooting](docs/TROUBLESHOOTING.md), [customization](docs/CUSTOMIZATION.md), provider support, and the AI at Home community channels. External links are opened only after an explicit click; no social or documentation service is contacted during dashboard startup.

QuotaCompass is MIT licensed. See `CHANGELOG.md`, `PLAN.md`, `docs/SECURITY.md`, `docs/PUBLISHING.md`, `docs/COMPLETION_AUDIT.md`, and `IMPLEMENTATION_NOTES.md` for release, design, risk, publication, and handoff context.

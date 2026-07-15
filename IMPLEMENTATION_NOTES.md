# QuotaCompass implementation notes

Concise handoff context for an agent entering this folder without conversation history. `PLAN.md` rev 9 is the product contract; `docs/COMPLETION_AUDIT.md` maps its gates to evidence.

## Implemented architecture

- Python 3.11+ package with FastAPI, platform-standard config/state paths, atomic JSON/Markdown state, WAL SQLite history, retention pruning, and a React/TypeScript dashboard bundled in the wheel.
- One server process owns polling. A PID/host/port file prevents a second live server and makes CLI queries use the running REST API. `status --poll` routes refresh through the server; `--force` explicitly warns before direct duplicate polling.
- Polling is concurrent and isolated, with a global limit, hard per-attempt timeout, two bounded attempts, exponential delay, `Retry-After` support capped at 60 seconds, and last-known-good retention.
- Manual values work for every provider as a true fallback during stale/error states and yield back automatically after upstream recovery. Absolute reset and DST-safe daily/weekly cadence entry are supported in CLI/API/UI.
- Advisor scoring is deterministic and explainable: headroom, reset urgency, short-window recovery, temporary-capacity bonuses bounded by the tightest metered window, health penalties, user priority, optional task capability weights, and linked-account deduplication.
- `doctor` emits stable IDs, codes, repair hints, service/port/state checks, credential reachability, and bounded live adapter fetches. Exit codes are 0 healthy, 3 stale/error, and 4 expired authentication.
- Reauthentication selects only fixed packaged scripts, rejects unknown paths/symlinks, rate-limits launches, writes a secret-free audit, and permits REST triggers only under configured local/remote policy. UI buttons appear only for adapters with an actual fixed helper.
- Setup is dry-run by default, detects native/WSL credential stores without copying credentials, enumerates and reports native/WSL TCP listeners, excludes detected plus user-reserved ports, prints final dashboard/API/state locations, supports non-interactive JSON, and runs doctor after writing. Detected Hermes/OpenClaw installs receive structured local/published install guidance plus environment-correct URL/state keys; setup never installs them. Setup emits structured review/install/uninstall service guidance but never executes it. The packaged helpers cover Windows Scheduled Tasks, Linux systemd user units, and macOS launchd; Windows review uses WhatIf and Unix review renders a no-write preview.
- Dashboard supports a ten-provider demo matrix, recommendation/nudges, provider windows, a filtered seven-day reset timeline with collision grouping plus exact chronological agenda, manual fallback, accessible history sparklines with inferred reset markers and numeric tables, auth repair, themes, responsive layouts, background refresh, scoped bearer-token entry, and an accessible resource menu for local/API help plus user-invoked community links. Runtime assets are entirely local.
- Shared Hermes/OpenClaw skill source and stdlib query helper generate both target packages. Resolution order is CLI, local REST, then `current.json`.

## Provider verification

- Stable: Claude OAuth, Codex OAuth, manual.
- Beta: Cursor.
- Experimental: OpenCode, Nous, Anthropic Admin, OpenRouter, Copilot, Gemini, xAI.
- Live verification succeeded for Codex, Cursor, and Nous. On 2026-07-12, Codex returned a valid weekly primary window and an explicitly null secondary window; QuotaCompass normalized this narrowly as a temporary unmetered 5-hour lane while retaining the weekly cap.
- Claude reached the provider endpoint, but the current credential returned 401; normalization and reauth guidance are verified, while refreshed live percentage comparison remains open.
- Other experimental adapters have redacted fixtures and honest manual/auth-only fallback where the provider lacks a stable quota surface. See `docs/PROVIDERS.md`.

## Security/privacy invariants

- No telemetry, hosted backend, leaderboard, cross-machine sync, Google dependency, CDN, analytics SDK, or third-party dashboard runtime.
- Provider polling requires internet access; state/history remain local.
- Never persist or log provider tokens, cookies, authorization headers, or refresh credentials.
- Loopback is the default. Non-loopback requires a read bearer token. Remote reauthentication requires a distinct token; the read token lives only in `sessionStorage`, while the reauth token exists only in form memory for one attempt. Setup output redacts both.
- Failures never erase provenance or silently turn unknown/unavailable states into zero usage.

## Verification snapshot (2026-07-12)

- Ruff: clean across the repository.
- Backend: all 85 unique tests pass. Preserved name-clash files remain excluded without deletion. Regression coverage now also locks the PEP 639 MIT metadata and token-free TestPyPI/PyPI publication boundaries, alongside serialized write-time reset countdowns, authentication-attention Markdown, provider HTTPS-host policy enforcement and deceptive-host rejection, conservative Codex temporary-capacity detection, advisor weekly-cap bounding, service poll serialization, Windows PID ownership, ten-provider demo breadth, inferable history resets, distinct read/reauth authorization, secret-redacted setup output, built-index asset resolution, and wheel/sdist name-clash exclusion.
- Frontend: TypeScript and Vite production build pass, 25 modules, approximately 214 kB JavaScript before gzip. Seven pinned Vitest/jsdom tests run axe-core WCAG 2.2 AA structural rules (including the open resource menu), reject serious/critical violations, assert same-origin requests, verify documentation/social destinations, exercise keyboard-only menu/theme/manual flows, test timeline filters and collision labels, verify inferred reset chart/table parity, and prove the remote reauth token never enters browser storage. They found and fixed a critical missing ARIA meter value. Real-browser QA at 375/768/1024/1440 confirmed no horizontal overflow, no undersized visible controls after setting the home link to a 44px minimum height, correct light/dark computed theme state, resource-menu Escape/focus return, timeline filtering, history reset parity, and a clean console. Pixel-based contrast and a complete manual keyboard traversal remain release checks.
- Registry availability: direct checks on 2026-07-12 returned 404 for exact quotacompass packages on PyPI and npm; GitHub exact repository-name search returned zero matches. Availability must still be rechecked immediately before publication.
- Dependency hardening: frontend versions are exactly pinned, build tooling is separated from the React runtime dependencies, and an offline frozen-lockfile install passes with pnpm 11.7.0. pnpm audit and an audit of the exact 21-package public transitive Python dependency closure reported no known vulnerabilities on 2026-07-12; the unpublished QuotaCompass root package was excluded from external submission.
- CI uses the same pnpm 11.7.0 version and enforces the frozen lockfile plus dashboard build across Windows, macOS, and Linux. The Scheduled Task PowerShell and systemd/launchd shell installers pass their native non-executing syntax parsers.
- Fresh-wheel acceptance on 2026-07-12: a clean Python 3.12 venv installed the exact promoted wheel and dependencies; CLI help passed; setup dry-run wrote nothing; explicit setup detected native/WSL stores without copying credentials; doctor correctly reported stopped service, missing snapshot, expired Claude auth, and live Codex/Cursor/Nous success; an actual loopback Uvicorn demo served dashboard/API HTTP 200 with ten providers, canonical static assets, and the local-only CSP. All temporary state was removed.
- Real-machine setup inventory reports native and Ubuntu WSL listeners, excludes their union from port selection, and emits suggested port plus dashboard/API/status/current.json/current.md locations without writing configuration.
- Focused coverage includes task scoring/recovery, linked accounts, Retry-After, manual fallback/cadence/DST, live doctor, reauth allowlist/audit, API filtering/auth, privacy assets, WSL discovery, scheduler, and skill generation.
- Native skill validation on 2026-07-12: Hermes 0.18 discovered the generated package as a local, trusted, enabled skill in an isolated WSL home. After adding its declared terminal requirement and `${HERMES_SKILL_DIR}` invocation, a real non-delivering Hermes one-shot correctly reported the recommendation, percentages/resets, temporary Codex capacity, expired Cursor auth, and both pre-reset nudges. OpenClaw 2026.6.8 likewise reported the skill eligible, model-visible, user-invocable, command-visible, and free of missing requirements; a real turn and exact /quotacompass command returned correct full reports. Marker-owned test copies were moved out of active skill roots and disposable services were stopped.
- Final sdist/wheel artifacts were rebuilt after the Hermes/menu work and the requirement-audit remediation; a release audit also caught a OneDrive-generated `assets (# Name clash ...)` path. Both build targets now exclude every preserved name-clash path, and a regression proves each index asset reference resolves. The exact wheel promoted to `dist` passed an isolated Python 3.12 install, CLI/setup dry-run, and packaged dashboard/API/CSP/static HTTP checks. It contains 64 files, three correctly addressed local static assets, all 12 reauth scripts, byte-identical packaged Hermes/OpenClaw skill sources, Windows tzdata metadata, no prohibited analytics/font/CDN endpoints, and no obvious embedded API-key pattern. The public sdist excludes the private initial design chat and every conflict copy. Strict Twine 6.2 checks pass. Final promoted hashes belong in the external release handoff rather than this packaged file so the sdist does not document a self-invalidating hash.

## Publication snapshot (2026-07-13)

- Public repository: `https://github.com/AIAtHome-Adam/QuotaCompass`; default branch `main`, issues and private vulnerability reporting enabled.
- `v0.1.0` is published as a GitHub prerelease/public alpha from commit `f5c9260`. Its exact CI run passed the package job and Python 3.11/3.13 matrices on Ubuntu, Windows, and macOS.
- CI found and fixed two real portability defects before release: the reauth helper test now expects `.ps1` on Windows and `.sh` elsewhere, and the cooldown now applies only after a prior launch rather than treating low system uptime as a recent launch.
- The green-CI wheel and sdist passed strict Twine checks, public-download digest verification, a clean Python 3.12 install, and packaged dashboard/API smoke tests (HTTP 200, health `ok`, ten demo providers).
- Windows sandbox caution: run Git metadata/index operations in the same elevated execution context. A split-root sandbox inconsistency once presented every tracked file as both staged-deleted and untracked; commit `8356697` immediately restored the intact tree. Verify `git status`, staged stats, and remote contents before future pushes.
- CI and publication workflows use current Node 24-compatible action majors; the former Node 20 deprecation warnings are retired.

## PyPI release preparation (2026-07-14)

- MIT remains the project license. Version 0.1.1 uses current PEP 639 metadata (`license = "MIT"` plus `license-files = ["LICENSE"]`) and Hatchling 1.27+; no account email is published in package metadata.
- `.github/workflows/publish.yml` builds and strictly audits one artifact set, sends manual dispatches only to TestPyPI, and sends only non-prerelease GitHub releases to PyPI. Both use OIDC Trusted Publishing rather than stored API tokens, and production is intended to have a required-reviewer `pypi` environment.
- Exact one-time publisher fields and the release procedure are in `docs/PUBLISHING.md`. PyPI and TestPyPI account security/configuration remain human-controlled.
- All GitHub Action majors used by CI and publishing were refreshed to their current Node 24-compatible generations during this work.
- Git work after the Windows split-root index incident is being performed from the clean checkout at `C:\Users\ITGAdmin\Documents\Workspaces\QuotaCompass-clean`. The original `QuotaCompass` folder, its ignored/private conflict files, and its running preview remain untouched. Verify the active checkout and `git status` before every commit or push.

## Human/external review queue

1. Refresh Claude auth and compare live 5-hour, weekly, model-scoped, and extra-usage windows against the provider UI.
2. Finish pixel-based contrast checks in both themes and a complete manual keyboard traversal. Real-browser layout QA at 375/768/1024/1440, theme switching, touch-target sizing, representative keyboard flows, history/timeline parity, and console health now pass.
3. Enable PyPI 2FA, register the pending publishers described in `docs/PUBLISHING.md`, publish 0.1.1 through the protected workflow, and verify a stranger install from PyPI; do not store a long-lived PyPI token locally.
4. Publish to Hermes Skills Hub and ClawHub, then verify stranger installs. Real Hermes and OpenClaw conversations plus the exact `/quotacompass` command already pass against synthetic exact-wheel data.
5. Review and explicitly run the chosen service installer; setup intentionally does not create a background service silently.
6. Resolve or archive the pre-existing and generated `# Name clash ...` conflict paths separately. They were preserved as user/workspace files and excluded from both release artifacts.

## Useful commands

```text
python -m ruff check . --no-cache
python -m pytest -p no:warnings
python -m build
cd web && pnpm run build
python skills/build_skills.py
python -m quotacompass setup --non-interactive --json
python -m quotacompass serve --demo
```

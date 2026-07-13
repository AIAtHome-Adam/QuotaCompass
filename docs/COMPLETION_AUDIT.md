# QuotaCompass completion audit

This matrix maps `PLAN.md` rev 9 to current evidence. Local implementation is distinguished from external acceptance actions; generated packages do not prove registry publication or real-agent behavior.

## Phase gates

| Phase | Requirement | Evidence | Status |
|---|---|---|---|
| 0 | Installable package, CLI, zero-telemetry posture, name/license decision | `pyproject.toml`, `LICENSE`, CI/build and wheel scans | Implemented and locally verified. Direct PyPI/npm/GitHub checks found the exact name unclaimed on 2026-07-12; availability and the MIT choice still require release-time confirmation. |
| 1 | Normalized model, atomic state, history, Claude/Codex vertical slice | Models/state/store tests, fixtures, serialized reset countdown tests, docs/PROVIDERS.md live log | Core verified; Codex live verified, including the temporary-capacity shape. Refreshed Claude percentage/UI comparison remains external because the current credential returned 401. |
| 2 | Remaining adapters, auth lifecycle, discovery, etiquette, manual fallback | Registry/adapter fixtures, WSL tests, retry/timeout/concurrency tests, fallback tests | Implemented. Cursor/Nous live verified; experimental adapters use allowed fixture/manual fallback posture. |
| 3 | REST API and decision-first accessible dashboard | API tests, production TypeScript/Vite build, ten-provider demo-state matrix, local CSP/privacy tests, pinned axe-core WCAG 2.2 AA structural audit, same-origin assertion, reset timeline/filter/collision tests, history chart/table reset-parity test, resource-menu link/Escape tests, keyboard theme/manual-flow tests, and real-browser QA at 375/768/1024/1440 | Implemented and CI-enforced. Desktop has a proportional seven-day reset strip with collision grouping and provider filters; mobile retains the exact chronological agenda. History charts label inferred resets and mirror them in the table. The requested help/community menu is responsive and explicit-click only. Automated DOM audit has no serious/critical violations and fixed a critical ARIA meter defect. Real-browser QA confirmed no horizontal overflow or undersized visible controls after raising the home link to a 44px touch target, both themes render, menu Escape returns focus, and the browser console is clean. Full traversal and pixel-based contrast remain release checks. |
| 4 | Wizard, service installers, doctor | Wizard tests/smoke, scoped-token redaction test, Scheduled Task/systemd/launchd scripts, stable doctor checks and live-fetch tests | Implemented. Exact-wheel fresh-environment setup dry-run/write, native/WSL listener inventory and collision avoidance, final URL/state output, secret-redacted proposals, actionable detected-agent guidance, doctor diagnostics/live probes, and real loopback demo HTTP pass; both installer scripts pass native non-executing syntax validation. Installers intentionally are not executed automatically. |
| 5 | Shared Hermes/OpenClaw skill and public distribution | Shared body/helper, generator, target trees, drift/fallback tests, isolated native discovery, real Hermes/OpenClaw non-delivering turns and /quotacompass command | Local packages and exact-wheel guidance paths pass. Hermes 0.18 and OpenClaw 2026.6.8 correctly reported recommendation, percentages/resets, temporary Codex capacity, auth failure, and nudge data from a synthetic exact-wheel dashboard; /quotacompass also returned a correct report. Authenticated registry publication and stranger install remain external release gates. |
| 6 | Explainable advisor, task hints, linked-account dedupe, agent/security/provider docs | Advisor/API/CLI tests and `docs/AGENTS.md`, `SECURITY.md`, `PROVIDERS.md` | Implemented and locally verified. Real Claude pre-reset reminder depends on refreshed live Claude data. |

## Cross-cutting evidence

| Requirement | Evidence | Status |
|---|---|---|
| Single poll owner / no accidental duplicate requests | PID runtime file, duplicate-server rejection, coordinated CLI tests, warned `--force` | Verified. |
| Bounded polite polling | 15-minute/5-minute-floor config, jitter scheduler, concurrency semaphore, timeouts, two attempts, exponential/`Retry-After` tests | Verified. |
| Honest fallback and provenance | Last-known-good and manual fallback tests; explicit quota/fetch/auth/source states | Verified. |
| UTC-offset timestamps and DST-safe cadence | `core/cadence.py`, IANA timezone config/tzdata, DST-crossing tests | Verified. |
| Local-only runtime | CSP, privacy and asset-resolution tests, session-only token wrapper, same-origin dashboard fetch test, explicit per-adapter HTTPS host allowlists, transport-boundary rejection tests, no prohibited asset references | Verified in source, production bundle, and final wheel; every built index asset resolves, name-clash paths are excluded, and deceptive subdomains, cleartext HTTP, undeclared telemetry hosts, and external dashboard API targets are rejected. |
| Credentials not persisted/logged | Normalized boundaries, redacted fixtures/setup proposals, audit tests, read-token session storage, one-attempt in-memory reauth token test | Covered; final secret scan remains prudent release practice. |
| Fixed reauth attack surface | Helper allowlist, path/symlink checks, cooldown, distinct read/reauth remote scopes, constant-time token checks, one-attempt browser handling, automatable-hint tests | Verified. |
| Agent handoff | `IMPLEMENTATION_NOTES.md` plus this matrix | Present. |
| Dependency supply chain | Exact frontend pins plus frozen-lockfile install; `pnpm audit`; exact public transitive Python dependency audit | No known vulnerabilities found on 2026-07-12. |

## Genuine remaining gates

- Refresh and live-compare Claude data.
- Finish a manual full-keyboard traversal and pixel-based contrast pass. Real-browser QA at 375/768/1024/1440 now proves no horizontal overflow, no undersized visible controls, correct theme switching, resource-menu Escape/focus return, history reset parity, timeline filtering, and a clean console.
- Authenticated Hermes Skills Hub/ClawHub publication and stranger-install verification. Hermes/OpenClaw conversations, nudge behavior, and /quotacompass behavior pass locally.
- Create the planned `AIAtHome-Adam/QuotaCompass` repository so in-app help links resolve, then make the release-time name/license and service-installation choices.

These require credentials, interactive external tools, publication identity, or a functioning browser execution environment. They are not represented as complete by local tests.

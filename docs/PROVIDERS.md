# Provider support and verification log

Support tiers describe interface stability, not provider endorsement. Unofficial endpoints can drift without notice; failures remain isolated and last-known-good state is marked stale.

| Adapter | Tier | Data source | Current verification |
|---|---|---|---|
| Claude OAuth | stable | Unofficial OAuth usage endpoint | Live request reached provider on 2026-07-10; the local credential returned 401 and was correctly classified expired. Fixture covers 5-hour, seven-day, model-scoped, and extra-usage shapes. |
| Codex OAuth | stable | Native OAuth rate-limit surface | Live verified with normal 5-hour + weekly windows and, on 2026-07-12, a weekly primary + explicitly null secondary shape. The latter is conservatively reported as a temporary unmetered 5-hour lane while the weekly cap remains authoritative. |
| Cursor | beta | Unofficial dashboard usage endpoint | Live verified on 2026-07-10 with monthly percentage and reset. Electron credential extraction remains brittle. |
| OpenCode | experimental | Local derived data | Fixture verified; no current native installation was detected for live comparison. |
| Nous | experimental | Hermes account endpoint | Live verified on 2026-07-10, including free-plan/unlimited display and expiring auth. |
| Anthropic Admin | experimental | Official Admin API | Recorded fixture verified; requires an organization Admin API key. |
| OpenRouter | experimental | Official key/credits APIs | Recorded fixtures verified; credit limits may be absent and are then reported as unknown percentage with remaining credits. |
| GitHub Copilot | experimental | Unofficial entitlement/usage surface | Recorded fixture verified; auth-only/manual fallback remains acceptable when the surface drifts. |
| Gemini | experimental | Native auth discovery + manual quota | Auth detection and manual fallback verified; no stable percentage endpoint is claimed. |
| xAI | experimental | Official management API + manual fallback | Fixture verified for management credentials; subscription-only users use manual state. |
| Manual | stable | User-entered local state | Persistence and API/UI/CLI update flows are tested. |

Provider endpoint and credential-path research was cross-checked against [mm7894215/TokenTracker](https://github.com/mm7894215/TokenTracker) as prior art, then isolated behind QuotaCompass adapters and redacted fixtures.

## Adding an adapter

Implement `Adapter.probe`, `fetch_usage`, and `close`; register the class in `adapters/registry.py`; normalize every window with a stable `window_id`, explicit `quota_state`, UTC-offset reset timestamp, freshness, provenance, and support tier. Add redacted fixture tests for success, auth expiry, malformed data, and network failure. Never include raw credentials in exceptions or `raw_extras`.

Each provider should retain a manual fallback so an upstream change degrades accuracy rather than removing visibility.

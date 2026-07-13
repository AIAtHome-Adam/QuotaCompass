# QuotaCompass instructions for agents

QuotaCompass is advisory. It does not proxy model traffic, and its local state may be read even when the server is stopped.

## Query order

1. Prefer `quotacompass status --json`, `quotacompass suggest --json`, or `quotacompass nudges --json`.
2. Use `quotacompass suggest --task agentic|chat|bulk --json` when the user provides a workload hint; capability weights are configuration, not hardcoded product opinion.
3. If the CLI is unavailable, query `GET /api/v1/status`, `/api/v1/suggest`, or `/api/v1/nudges` on the configured local URL. Send `Authorization: Bearer $QUOTACOMPASS_TOKEN` only when configured.
4. Otherwise run `quotacompass paths --json` to locate `current.json`, or use the state path supplied by the operator.
5. If none work, run `quotacompass doctor --json` and surface failing check IDs with their hints.

## Interpretation rules

- Compare the current time to each provider's `stale_after`. Recompute reset countdowns from `resets_at`; any stored relative countdown was only correct when generated.
- `quota_state` distinguishes `metered`, `unlimited`, `unknown`, and `unavailable`. Never interpret `used_pct: null` as zero.
- `estimated: true` identifies derived or manually entered data.
- `fetch_status: stale` may contain retained last-known-good windows. Explain that qualification.
- Prefer `advisor.suggestion`, but state its ranking reason and respect exclusions. Entries excluded by `linked_account` share the same underlying capacity.
- Never ask for or expose provider credentials. QuotaCompass reads native stores at poll time.

## Reminder prompt

> Check `quotacompass nudges --json`. If any window is more than 25% unused and resets within 24 hours, remind me which provider and window to use, including the reset time. Stay silent when there are no nudges.

Reauthentication is a user-directed repair action. Explain that `quotacompass reauth <id>` launches a fixed native login helper, then run it only if requested and locally permitted.

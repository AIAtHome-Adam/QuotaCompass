---
name: quotacompass
description: Check local AI subscription and API quota usage, reset times, provider suggestions, expiring-unused nudges, and authentication health. Use when choosing an AI provider or asking how much quota remains.
license: MIT
compatibility: Requires Python 3 and access to a local QuotaCompass CLI, API, or current.json state file.
metadata:
  author: QuotaCompass contributors
  version: "0.1.0"
  openclaw:
    emoji: "🧭"
    requires:
      anyBins: [python3, python]
---

# QuotaCompass

Use this skill when someone asks about AI quota, usage percentages, reset times, expiring unused allowance, authentication health, or which configured provider to use for a task.

## Quick reference

- `status`: full provider and advisor snapshot
- `suggest`: recommendation and ranking with score reasons
- `nudges`: allowance likely to expire unused soon
- The standalone dashboard URL is normally `http://127.0.0.1:4747/`.

## Procedure

1. Use the terminal tool. In Hermes, run `python3 ${HERMES_SKILL_DIR}/scripts/query.py status`; in OpenClaw, run `python3 scripts/query.py status` from this skill directory. If only `python` exists, use it instead.
2. For a provider choice, run `python3 scripts/query.py suggest`. For pre-reset reminders, run `python3 scripts/query.py nudges`.
3. Report freshness and authentication problems before interpreting percentages.
4. For each metered window, explain `used_pct`, the absolute `resets_at` time, and remaining quota (`100 - used_pct`). Preserve the timestamp offset when quoting it.
5. Use `advisor.suggestion` as the default recommendation, but include its ranking reason and exclusions. Unknown, unavailable, unlimited, stale, and failed states are not interchangeable.
6. If the user wants a visual view, provide the configured dashboard URL. Do not claim the dashboard is offline when provider polling requires internet access; it is local-only and has no telemetry or cloud service.

The helper resolves data in this order: installed QuotaCompass CLI, local REST API, then the state file. Optional overrides are `--url`, `--state-file`, and environment variables `QUOTACOMPASS_URL`, `QUOTACOMPASS_TOKEN`, and `QUOTACOMPASS_STATE_FILE`.

## Acting on results

- To update a manual provider, use `quotacompass set <provider> --window weekly --used-pct <0-100> --resets-at <ISO-8601>`.
- Reauthentication launches only a fixed local provider helper. Before the first attempt, tell the user it starts the provider's native login flow. Run `quotacompass reauth <provider>` only when the user asked to repair authentication and local reauth is enabled.
- Never request, print, copy, or store provider tokens. QuotaCompass reads native credential stores itself.

## Pitfalls

- Recompute freshness from each provider's `stale_after` compared with the current time. Do not treat an old generated countdown as current.
- `used_pct: null` must be interpreted with `quota_state`; it does not automatically mean zero usage.
- `estimated: true` means the value was derived or manually entered.
- Providers excluded because of `linked_account` are duplicate views of one underlying quota, not extra capacity.
- If all resolution methods fail, recommend `quotacompass doctor` and quote its failing check IDs and fix hints.

## Verification

Confirm the output is JSON with `schema_version`, `generated_at`, `providers`, and `advisor` for status queries. A successful suggestion must either name a provider present in the ranking or explicitly return no recommendation. A nudge must include provider ID, window, unused percentage, and reset timestamp.

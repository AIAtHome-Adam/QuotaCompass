# Customization

Run `quotacompass paths --json` to locate the active configuration file. Copy values from `config.example.yaml` and override only what you need.

## Dashboard and storage

- `timezone` controls display and cadence interpretation.
- `server.host` and `server.port` control the local dashboard. Keep the default loopback host unless remote access is intentional; non-loopback binds require `server.auth_token`.
- `security.reauth_trigger` controls whether native login helpers are disabled, loopback-only, or remotely triggerable.
- Remote reauthentication requires `security.reauth_token`, which must differ from `server.auth_token`; ordinary API access and login-launch authority are deliberately separate.
- `state.dir` selects a custom local state directory.
- `state.history_retention_days` controls local history retention.
- `reserved_ports` keeps setup from proposing ports used by your other tools.

## Polling

- `poll.default_interval_minutes` sets the normal refresh cadence.
- `poll.concurrency` bounds simultaneous provider requests.

Keep polling considerate. QuotaCompass applies timeouts, jitter, bounded retries, and `Retry-After`; aggressive intervals can still cause provider throttling without making quota data more useful.

## Providers and manual fallback

Provider-specific settings live under `providers`. Use `quotacompass set` for a manual window when an upstream source is unavailable, for example:

```text
quotacompass set manual-provider --window weekly --used-pct 35 --cadence "weekly:thu 23:59" --timezone America/Denver
```

Live data takes precedence when the provider recovers. See [Provider support](PROVIDERS.md) before enabling an experimental adapter.

## Advisor and reminders

- `advisor.nudge_threshold.unused_pct` is the minimum unused allowance worth mentioning.
- `advisor.nudge_threshold.within_hours` limits reminders to windows resetting soon.
- `advisor.task_weights` adjusts provider scoring for named task hints used by `quotacompass suggest --task <name>`.

After editing configuration, run `quotacompass doctor` and a foreground `quotacompass poll` before restarting a background service.

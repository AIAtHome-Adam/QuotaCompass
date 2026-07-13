# Troubleshooting

Start with `quotacompass doctor`. It checks prerequisites, state freshness, service ownership, and bounded provider access, and gives a repair hint for each failed check.

## Dashboard does not open

- Run `quotacompass paths --json` to confirm the configured dashboard address and state paths.
- Start a foreground server with `quotacompass serve`, then open the printed loopback URL.
- If the preferred port is occupied, run `quotacompass setup` to preview a safe alternative and `quotacompass setup --write` to accept it.
- For a non-loopback bind, configure `server.auth_token`; QuotaCompass intentionally rejects an unauthenticated network-facing dashboard.

## Data is stale or a provider failed

- Run `quotacompass status --poll --json` for a fresh provider attempt and inspect `fetch_status`, `fetch_error`, and `last_success_at` separately.
- Follow the provider's `user_action` when authentication is expired. Run `quotacompass reauth <provider>` only when you intend to start that provider's native sign-in flow.
- Use a manual value while an upstream surface is unavailable. Live data automatically takes precedence again after recovery.
- See [Provider support](PROVIDERS.md) for support tiers, endpoint provenance, and known fallbacks.

## The dashboard asks for an API token

This is expected when `server.auth_token` is configured. Enter that QuotaCompass read/API token - not a provider credential. The dashboard stores it only in the current tab's `sessionStorage` and sends it only to the same origin.

If a remote reauthentication action asks for a second token, enter the distinct `security.reauth_token`. It is held in form memory for one attempt and is never saved in browser storage. The ordinary read token cannot launch a native login flow.

## WSL and native Windows disagree

Run `quotacompass setup` from the environment that will own the service. Its dry-run report checks native and WSL listeners before proposing a port. Avoid starting a second poller against the same account; normal CLI refresh commands reuse a running server.

## Still stuck

Capture `quotacompass doctor`, `quotacompass status --json`, the QuotaCompass version, OS, and installation method. Remove tokens, cookies, and authorization headers before sharing a report. Security-sensitive reports should follow [Security and privacy](SECURITY.md#reporting).

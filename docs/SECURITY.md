# Security and privacy

QuotaCompass has no telemetry, analytics SDK, hosted backend, leaderboard, remote account, or third-party dashboard asset. Provider polling necessarily uses the network; every networked adapter declares an HTTPS hostname allowlist enforced before transport, while application state and history remain local.

## Credential handling

- Adapters read the provider's native credential store at poll time. QuotaCompass does not copy credentials into its config, state JSON, Markdown, SQLite history, or logs.
- API-key adapters accept environment/config references supported by their native workflow; do not commit populated configuration.
- Normalized output and tests must never contain access tokens, refresh tokens, cookies, or authorization headers.

## Network exposure

- The server defaults to loopback. A non-loopback bind is rejected unless `server.auth_token` is set.
- Static assets are bundled, and the dashboard Content Security Policy rejects external runtime content. Provider HTTP calls reject cleartext URLs, deceptive subdomains, and hosts outside the adapter-specific allowlist before a request reaches the transport.
- The ordinary API/read bearer token is kept only in tab-scoped `sessionStorage`, sent to the same origin, and never written to quota state or history. A remote reauthentication token is held only in form memory for one attempt and is never placed in browser storage.
- Treat quota history as sensitive behavioral data even though it contains no prompts or model responses.

## Reauthentication boundary

`security.reauth_trigger` defaults to `local`. `off` disables the REST trigger. `remote` requires both `server.auth_token` for ordinary API access and a distinct `security.reauth_token` for the higher-risk launch action. The read token cannot authorize reauthentication, and the reauth token cannot read quota APIs. Setup output redacts both values. Requests can select only a configured provider; they cannot supply a command or script path. Helpers resolve from a fixed packaged directory, reject symlinks, apply a cooldown, and write a credential-free audit event.

QuotaCompass never performs background token refresh. Native login helpers are visible, user-directed flows.

## Reporting

Use [GitHub private vulnerability reporting](https://github.com/AIAtHome-Adam/QuotaCompass/security/advisories/new) rather than a public issue. Before submitting, remove credentials, account IDs, machine paths, and raw provider responses. Include the adapter name, support tier, QuotaCompass version, failing `doctor` check ID, and a minimal redacted reproduction.

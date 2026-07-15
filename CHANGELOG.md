# Changelog

All notable changes to QuotaCompass are recorded here. The project follows semantic versioning after its initial public alpha.

## [0.1.1] - 2026-07-14

### Changed

- Declared the existing MIT license with current SPDX/PEP 639 package metadata and explicitly bundled `LICENSE`.
- Added token-free PyPI and TestPyPI Trusted Publishing with isolated environments, single-build artifact promotion, strict distribution checks, and release-tag/version validation.
- Updated GitHub Actions to Node 24-compatible action majors and documented a repeatable publishing and clean-install verification procedure.

## [0.1.0] - 2026-07-12

### Added

- Local-first quota collection, normalization, history, and advisory scoring for ten provider lanes with honest manual fallback.
- CLI, REST API, Markdown/JSON state, demo mode, doctor diagnostics, and packaged user-service helpers.
- Decision-first responsive dashboard with light/dark themes, reset timeline and collision grouping, history reset markers, authentication repair guidance, and local documentation/community navigation.
- Conservative detection of temporary OpenAI short-window capacity boosts while retaining the weekly limit.
- Shared Hermes and OpenClaw agent skills with CLI, REST, and state-file fallback.

### Security and privacy

- No telemetry, hosted backend, cloud account, leaderboard, analytics SDK, CDN, or third-party runtime asset.
- Provider credentials are read in place and excluded from normalized state, history, logs, and setup proposals.
- Loopback-only defaults, explicit provider host allowlists, Content Security Policy, and distinct read/remote-reauth tokens.

### Known limitations

- Several providers expose unofficial or account-dependent quota surfaces and may require manual fallback after upstream changes.
- Registry publication for the optional Hermes and OpenClaw skills is tracked separately from the core Python package release.
- This is the first public alpha; feedback-driven compatibility fixes will ship as 0.1.x releases.

[0.1.0]: https://github.com/AIAtHome-Adam/QuotaCompass/releases/tag/v0.1.0
[0.1.1]: https://github.com/AIAtHome-Adam/QuotaCompass/compare/v0.1.0...v0.1.1

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotacompass.core.advisor import advise
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    CapacityNotice,
    DataSource,
    FetchError,
    FetchState,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    ReauthHint,
    StateSnapshot,
    SupportTier,
)


def demo_snapshot(now: datetime | None = None) -> StateSnapshot:
    current = now or datetime.now(UTC)

    def provider(
        provider_id: str,
        label: str,
        windows: list[LimitWindow],
        *,
        auth: AuthState = AuthState.OK,
        fetch: FetchState = FetchState.OK,
        source: DataSource = DataSource.UNOFFICIAL_API,
        tier: SupportTier = SupportTier.STABLE,
        error: FetchError | None = None,
        notices: list[CapacityNotice] | None = None,
        auth_expires_at: datetime | None = None,
        reauth_automatable: bool = False,
        kind: str | None = None,
    ) -> ProviderStatus:
        return ProviderStatus(
            id=provider_id,
            label=label,
            kind=kind or ("manual" if source == DataSource.MANUAL else "subscription"),
            support_tier=tier,
            data_source=source,
            auth=AuthStatus(
                status=auth,
                expires_at=auth_expires_at,
                reauth=(
                    ReauthHint(command=f"{provider_id} login", automatable=True)
                    if reauth_automatable
                    else None
                ),
            ),
            windows=windows,
            capacity_notices=notices or [],
            fetched_at=current,
            last_success_at=current
            if fetch == FetchState.OK
            else current - timedelta(hours=2),
            fetch_status=fetch,
            fetch_error=error,
            stale_after=current + timedelta(minutes=30),
        )

    providers = [
        provider(
            "claude-pro",
            "Claude Pro",
            [
                LimitWindow(
                    window_id="claude:5h",
                    name="5h",
                    quota_state=QuotaState.METERED,
                    used_pct=38,
                    resets_at=current + timedelta(hours=2, minutes=12),
                    window_duration_seconds=18000,
                ),
                LimitWindow(
                    window_id="claude:weekly",
                    name="weekly",
                    quota_state=QuotaState.METERED,
                    used_pct=31,
                    resets_at=current + timedelta(hours=9),
                    window_duration_seconds=604800,
                ),
            ],
        ),
        provider(
            "codex",
            "ChatGPT / Codex",
            [
                LimitWindow(
                    window_id="codex:18000-promotion",
                    name="5h",
                    quota_state=QuotaState.UNLIMITED,
                    window_duration_seconds=18000,
                    temporary=True,
                    inferred=True,
                    status_note=(
                        "5-hour limit is temporarily unmetered; "
                        "the weekly limit still applies."
                    ),
                ),
                LimitWindow(
                    window_id="codex:weekly",
                    name="weekly",
                    quota_state=QuotaState.METERED,
                    used_pct=54,
                    resets_at=current + timedelta(days=4),
                    window_duration_seconds=604800,
                ),
            ],
            notices=[
                CapacityNotice(
                    notice_id="codex:short-window-unmetered",
                    kind="promotion",
                    title="Temporary capacity boost detected",
                    message=(
                        "5-hour limit is temporarily unmetered; "
                        "the weekly limit still applies."
                    ),
                    evidence="valid_weekly_window_with_explicitly_null_secondary_window",
                )
            ],
        ),
        provider(
            "nous",
            "Nous Portal",
            [
                LimitWindow(
                    window_id="nous:promo",
                    name="promo",
                    quota_state=QuotaState.UNLIMITED,
                )
            ],
            tier=SupportTier.EXPERIMENTAL,
        ),
        provider(
            "cursor",
            "Cursor",
            [
                LimitWindow(
                    window_id="cursor:monthly",
                    name="monthly",
                    quota_state=QuotaState.METERED,
                    used_pct=67,
                    resets_at=current + timedelta(days=12),
                )
            ],
            auth=AuthState.EXPIRED,
            fetch=FetchState.STALE,
            tier=SupportTier.BETA,
            error=FetchError(
                code="auth_expired",
                category="authentication",
                message="Sign in to Cursor to refresh quota data",
                user_action="Open Cursor and sign in",
            ),
        ),
        provider(
            "opencode",
            "OpenCode Go",
            [
                LimitWindow(
                    window_id="opencode:5h",
                    name="5h",
                    quota_state=QuotaState.METERED,
                    used_pct=91,
                    resets_at=current + timedelta(minutes=45),
                    window_duration_seconds=18000,
                    estimated=True,
                ),
                LimitWindow(
                    window_id="opencode:weekly",
                    name="weekly",
                    quota_state=QuotaState.METERED,
                    used_pct=48,
                    resets_at=current + timedelta(days=4),
                    window_duration_seconds=604800,
                    estimated=True,
                ),
            ],
            source=DataSource.LOCAL_DERIVED,
            tier=SupportTier.BETA,
        ),
        provider(
            "openrouter",
            "OpenRouter API credits",
            [
                LimitWindow(
                    window_id="openrouter:credits",
                    name="credits",
                    quota_state=QuotaState.METERED,
                    used_pct=22,
                )
            ],
            source=DataSource.OFFICIAL_API,
            tier=SupportTier.EXPERIMENTAL,
            kind="api",
        ),
        provider(
            "copilot",
            "GitHub Copilot",
            [
                LimitWindow(
                    window_id="copilot:monthly",
                    name="monthly",
                    quota_state=QuotaState.METERED,
                    used_pct=41,
                    resets_at=current + timedelta(days=6),
                )
            ],
            auth=AuthState.EXPIRING_SOON,
            auth_expires_at=current + timedelta(hours=18),
            reauth_automatable=True,
            tier=SupportTier.EXPERIMENTAL,
        ),
        provider(
            "gemini",
            "Gemini Code Assist",
            [
                LimitWindow(
                    window_id="gemini:quota",
                    name="quota",
                    quota_state=QuotaState.UNAVAILABLE,
                )
            ],
            auth=AuthState.UNKNOWN,
            fetch=FetchState.ERROR,
            tier=SupportTier.EXPERIMENTAL,
            error=FetchError(
                code="quota_surface_unavailable",
                category="provider",
                message="No stable percentage surface is available for this account",
                user_action="Enter the value shown by Gemini manually",
            ),
        ),
        provider(
            "xai",
            "xAI API credits",
            [
                LimitWindow(
                    window_id="xai:credits",
                    name="credits",
                    quota_state=QuotaState.METERED,
                    used_pct=72,
                    resets_at=current + timedelta(days=4),
                )
            ],
            source=DataSource.OFFICIAL_API,
            tier=SupportTier.EXPERIMENTAL,
            kind="api",
        ),
        provider(
            "manual-provider",
            "Manual provider with a deliberately long display name",
            [
                LimitWindow(
                    window_id="manual:weekly",
                    name="weekly",
                    quota_state=QuotaState.UNKNOWN,
                    estimated=True,
                )
            ],
            source=DataSource.MANUAL,
        ),
    ]
    return StateSnapshot(
        generated_at=current,
        providers=providers,
        advisor=advise(providers, now=current),
    )

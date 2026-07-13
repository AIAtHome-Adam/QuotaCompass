from datetime import UTC, datetime, timedelta

from quotacompass.core.advisor import advise
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    CapacityNotice,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    ReauthHint,
    StateSnapshot,
    SupportTier,
)
from quotacompass.core.statefile import render_markdown

NOW = datetime(2026, 7, 10, 18, tzinfo=UTC)


def provider(provider_id: str, used: float, reset_hours: int) -> ProviderStatus:
    return ProviderStatus(
        id=provider_id,
        label=provider_id.title(),
        kind="subscription",
        support_tier=SupportTier.STABLE,
        data_source=DataSource.UNOFFICIAL_API,
        auth=AuthStatus(status="ok"),
        windows=[
            LimitWindow(
                window_id=f"{provider_id}:weekly",
                name="weekly",
                quota_state=QuotaState.METERED,
                used_pct=used,
                resets_at=NOW + timedelta(hours=reset_hours),
            )
        ],
        fetched_at=NOW,
        last_success_at=NOW,
        stale_after=NOW + timedelta(minutes=30),
    )


def test_advisor_prefers_headroom() -> None:
    result = advise([provider("claude", 80, 72), provider("codex", 20, 72)], now=NOW)
    assert result.suggestion == "codex"
    assert result.ranking[0].breakdown.headroom > result.ranking[1].breakdown.headroom


def test_advisor_emits_expiring_unused_nudge() -> None:
    result = advise([provider("claude", 20, 3)], now=NOW)
    assert result.expiring_unused[0].id == "claude"
    assert result.expiring_unused[0].unused_pct == 80


def test_percentage_bounds_are_enforced() -> None:
    try:
        LimitWindow(
            window_id="bad", name="weekly", quota_state=QuotaState.METERED, used_pct=101
        )
    except ValueError:
        pass
    else:
        raise AssertionError("used_pct > 100 must fail validation")


def test_advisor_prioritizes_temporary_capacity_without_ignoring_weekly_cap() -> None:
    baseline = provider("codex", 20, 72)
    boosted = baseline.model_copy(
        update={
            "capacity_notices": [
                CapacityNotice(
                    notice_id="codex:short-window-unmetered",
                    kind="promotion",
                    title="Temporary capacity boost detected",
                    message=(
                        "5-hour limit is temporarily unmetered; "
                        "the weekly limit still applies."
                    ),
                )
            ]
        }
    )

    normal_rank = advise([baseline], now=NOW).ranking[0]
    boosted_rank = advise([boosted], now=NOW).ranking[0]

    assert boosted_rank.score > normal_rank.score
    assert boosted_rank.breakdown.promotion == 0.2
    assert "Temporary unmetered 5h lane detected" in boosted_rank.reason
    assert "80% remains in the weekly limit" in boosted_rank.reason

    exhausted = provider("codex", 100, 72).model_copy(
        update={"capacity_notices": boosted.capacity_notices}
    )
    assert advise([exhausted], now=NOW).ranking[0].breakdown.promotion == 0


def test_snapshot_serializes_reset_countdown_at_generation_time() -> None:
    snapshot = StateSnapshot(generated_at=NOW, providers=[provider("claude", 20, 2)])

    assert snapshot.providers[0].windows[0].resets_in_seconds == 7200
    payload = snapshot.model_dump(mode="json")
    assert payload["providers"][0]["windows"][0]["resets_in_seconds"] == 7200

    restored = StateSnapshot.model_validate(payload)
    assert restored.providers[0].windows[0].resets_in_seconds == 7200


def test_markdown_surfaces_expiring_authentication_action() -> None:
    item = provider("codex", 20, 72)
    item.auth = AuthStatus(
        status=AuthState.EXPIRING_SOON,
        expires_at=NOW + timedelta(days=2),
        reauth=ReauthHint(command="codex login", automatable=True),
    )
    rendered = render_markdown(StateSnapshot(generated_at=NOW, providers=[item]))

    assert "## Authentication attention" in rendered
    assert "Codex" in rendered
    assert "expiring soon" in rendered
    assert "codex login" in rendered
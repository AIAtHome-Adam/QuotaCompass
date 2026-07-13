from datetime import UTC, datetime, timedelta

from quotacompass.core.advisor import advise
from quotacompass.core.config import AdvisorConfig
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
)

NOW = datetime(2026, 7, 11, 18, tzinfo=UTC)


def provider(
    provider_id: str,
    used: float,
    *,
    duration: int | None = None,
    reset_hours: int = 8,
) -> ProviderStatus:
    return ProviderStatus(
        id=provider_id,
        label=provider_id,
        kind="subscription",
        data_source=DataSource.UNOFFICIAL_API,
        auth=AuthStatus(status=AuthState.OK),
        windows=[
            LimitWindow(
                window_id=f"{provider_id}:window",
                name="window",
                quota_state=QuotaState.METERED,
                used_pct=used,
                resets_at=NOW + timedelta(hours=reset_hours),
                window_duration_seconds=duration,
            )
        ],
        fetched_at=NOW,
        last_success_at=NOW,
        stale_after=NOW + timedelta(minutes=30),
    )


def test_task_capability_weight_changes_ranking_explainably() -> None:
    settings = AdvisorConfig.model_validate(
        {"task_weights": {"agentic": {"claude": 1.0, "codex": 0.2}}}
    )
    result = advise(
        [provider("claude", 40), provider("codex", 20)],
        settings,
        now=NOW,
        task="agentic",
    )

    assert result.suggestion == "claude"
    codex = next(item for item in result.ranking if item.id == "codex")
    assert codex.breakdown.capability == 0.2
    assert "capability weight 0.2" in codex.reason


def test_short_window_recovery_bonus_is_bounded_and_reported() -> None:
    result = advise(
        [provider("codex", 90, duration=5 * 3600, reset_hours=1)],
        now=NOW,
    )

    rank = result.ranking[0]
    assert 0 < rank.breakdown.recovery <= 0.15
    assert "recovers soon" in rank.reason

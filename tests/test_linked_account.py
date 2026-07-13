from datetime import UTC, datetime, timedelta

from quotacompass.core.advisor import advise
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
)


def linked_provider(provider_id: str, *, expired: bool = False) -> ProviderStatus:
    now = datetime.now(UTC)
    return ProviderStatus(
        id=provider_id,
        label=provider_id,
        kind="subscription",
        data_source=DataSource.UNOFFICIAL_API,
        auth=AuthStatus(status=AuthState.EXPIRED if expired else AuthState.OK),
        windows=[
            LimitWindow(
                window_id=f"{provider_id}:weekly",
                name="weekly",
                quota_state=QuotaState.METERED,
                used_pct=20,
                resets_at=now + timedelta(hours=2),
            )
        ],
        raw_extras={"linked_account": "shared-claude"},
        fetched_at=now,
        last_success_at=now,
        stale_after=now + timedelta(minutes=30),
    )


def test_advisor_deduplicates_linked_accounts() -> None:
    result = advise([linked_provider("native"), linked_provider("wsl", expired=True)])

    assert result.suggestion == "native"
    assert next(item for item in result.ranking if item.id == "wsl").excluded
    assert [item.id for item in result.expiring_unused] == ["native"]

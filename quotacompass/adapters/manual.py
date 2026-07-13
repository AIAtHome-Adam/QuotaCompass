from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult
from quotacompass.core.cadence import next_reset
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    SupportTier,
)


class ManualAdapter(Adapter):
    default_support_tier = SupportTier.STABLE
    default_data_source = DataSource.MANUAL

    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "Manual quota entry is always available")

    async def fetch_usage(self) -> ProviderStatus:
        now = datetime.now(UTC)
        configured = self.options.get("windows") or []
        if not configured:
            raise AdapterError(
                "manual_entry_missing",
                "No manual quota values have been entered",
            )
        windows: list[LimitWindow] = []
        for index, item in enumerate(configured):
            reset = item.get("resets_at")
            if reset:
                reset = datetime.fromisoformat(str(reset).replace("Z", "+00:00"))
            elif item.get("cadence"):
                reset = next_reset(
                    str(item["cadence"]),
                    str(item.get("timezone") or self.options.get("timezone") or "UTC"),
                    now=now,
                )
            state = item.get("quota_state") or (
                "metered" if item.get("used_pct") is not None else "unknown"
            )
            windows.append(
                LimitWindow(
                    window_id=item.get("window_id", f"{self.provider_id}:{index}"),
                    name=item.get("name", f"custom-{index + 1}"),
                    quota_state=QuotaState(state),
                    used_pct=item.get("used_pct"),
                    resets_at=reset,
                    window_duration_seconds=item.get("window_duration_seconds"),
                    estimated=bool(item.get("estimated", True)),
                )
            )
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="manual",
            support_tier=self.support_tier,
            data_source=DataSource.MANUAL,
            auth=AuthStatus(status=AuthState.UNKNOWN),
            windows=windows,
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

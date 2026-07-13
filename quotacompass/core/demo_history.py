from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotacompass.core.demo import demo_snapshot
from quotacompass.core.models import ProviderStatus


def demo_history(provider_id: str, days: int = 30) -> list[ProviderStatus]:
    now = datetime.now(UTC)
    provider = next((item for item in demo_snapshot(now).providers if item.id == provider_id), None)
    if provider is None:
        return []
    result: list[ProviderStatus] = []
    count = min(12, max(2, days))
    for index in range(count):
        recorded = now - timedelta(days=count - index - 1)
        item = provider.model_copy(deep=True)
        item.fetched_at = recorded
        item.last_success_at = recorded
        for window in item.windows:
            if window.used_pct is not None:
                cycle = index % 5
                drift = (cycle - 2) * 8.0
                window.used_pct = max(0.0, min(100.0, window.used_pct + drift))
        result.append(item)
    return result

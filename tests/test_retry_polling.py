import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from quotacompass.adapters.base import (
    Adapter,
    AdapterError,
    ProbeResult,
    retry_after_seconds,
)
from quotacompass.core.models import DataSource, ProviderStatus
from quotacompass.core.poller import poll_adapters


class RetryOnce(Adapter):
    def __init__(self, provider_id: str) -> None:
        super().__init__(provider_id)
        self.calls = 0

    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "test")

    async def fetch_usage(self) -> ProviderStatus:
        self.calls += 1
        if self.calls == 1:
            raise AdapterError(
                "rate_limited",
                "try later",
                retryable=True,
                retry_after=0.25,
            )
        now = datetime.now(UTC)
        return ProviderStatus(
            id=self.provider_id,
            label=self.provider_id,
            kind="test",
            data_source=DataSource.MANUAL,
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=5),
        )


def test_retryable_failure_honors_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("quotacompass.core.poller.asyncio.sleep", fake_sleep)
    adapter = RetryOnce("retry")

    result = asyncio.run(poll_adapters([adapter]))

    assert result[0].fetch_status == "ok"
    assert adapter.calls == 2
    assert delays == [0.25]


def test_retry_after_parses_seconds_and_http_date() -> None:
    now = datetime(2026, 7, 11, 18, tzinfo=UTC)

    assert retry_after_seconds("3.5", now=now) == 3.5
    assert retry_after_seconds("Sat, 11 Jul 2026 18:00:10 GMT", now=now) == 10
    assert retry_after_seconds("not-a-delay", now=now) is None

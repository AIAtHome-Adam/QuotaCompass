import asyncio
from datetime import UTC, datetime, timedelta

from quotacompass.adapters.base import Adapter, ProbeResult
from quotacompass.core.models import DataSource, ProviderStatus, SupportTier
from quotacompass.core.poller import poll_adapters


class Broken(Adapter):
    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "test")

    async def fetch_usage(self) -> ProviderStatus:
        raise RuntimeError("isolated")


class Working(Adapter):
    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "test")

    async def fetch_usage(self) -> ProviderStatus:
        now = datetime.now(UTC)
        return ProviderStatus(
            id=self.provider_id,
            label="Working",
            kind="manual",
            support_tier=SupportTier.STABLE,
            data_source=DataSource.MANUAL,
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(hours=1),
        )


def test_provider_failure_is_isolated() -> None:
    result = asyncio.run(poll_adapters([Broken("bad"), Working("good")]))
    assert [item.id for item in result] == ["bad", "good"]
    assert result[0].fetch_status == "error"
    assert result[1].fetch_status == "ok"

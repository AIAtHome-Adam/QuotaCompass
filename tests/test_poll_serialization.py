import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotacompass.adapters.base import Adapter, ProbeResult
from quotacompass.core.config import AppConfig
from quotacompass.core.models import DataSource, ProviderStatus
from quotacompass.core.service import QuotaService


class SlowAdapter(Adapter):
    def __init__(self, provider_id: str) -> None:
        super().__init__(provider_id)
        self.active = 0
        self.max_active = 0

    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "test")

    async def fetch_usage(self) -> ProviderStatus:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
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


def test_service_serializes_overlapping_poll_requests(tmp_path: Path) -> None:
    adapter = SlowAdapter("provider")
    service = QuotaService(AppConfig(), state_dir=tmp_path, adapters=[adapter])

    async def exercise() -> None:
        await asyncio.gather(service.poll(), service.poll())

    asyncio.run(exercise())

    assert adapter.max_active == 1

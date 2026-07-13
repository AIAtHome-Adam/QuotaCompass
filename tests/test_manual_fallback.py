import asyncio
from pathlib import Path

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult
from quotacompass.core.config import AppConfig
from quotacompass.core.service import QuotaService


class FailedUpstream(Adapter):
    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "fixture")

    async def fetch_usage(self):  # type: ignore[no-untyped-def]
        raise AdapterError("network_error", "offline", retryable=False)


def test_manual_values_survive_failed_upstream_poll(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"providers": {"provider": {"adapter": "claude_oauth"}}})
    service = QuotaService(
        config,
        state_dir=tmp_path,
        adapters=[FailedUpstream("provider")],
    )
    service.manual_entries.set(
        "provider",
        [
            {
                "name": "weekly",
                "quota_state": "metered",
                "used_pct": 37,
                "resets_at": "2026-07-17T23:59:00-06:00",
            }
        ],
    )

    snapshot = asyncio.run(service.poll())

    provider = snapshot.providers[0]
    assert provider.fetch_status == "error"
    assert provider.fetch_error and provider.fetch_error.code == "network_error"
    assert provider.data_source == "manual"
    assert provider.windows[0].used_pct == 37
    assert provider.raw_extras["manual_fallback"] is True

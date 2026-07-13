import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult
from quotacompass.core.config import AppConfig
from quotacompass.core.models import (
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    StateSnapshot,
    SupportTier,
)
from quotacompass.core.service import QuotaService
from quotacompass.core.statefile import write_snapshot
from quotacompass.server.app import create_app


class Failing(Adapter):
    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "fixture")

    async def fetch_usage(self) -> ProviderStatus:
        raise AdapterError("network_error", "temporary failure", retryable=True)


def previous(provider_id: str = "provider") -> ProviderStatus:
    now = datetime.now(UTC) - timedelta(minutes=10)
    return ProviderStatus(
        id=provider_id,
        label="Previous provider",
        kind="subscription",
        support_tier=SupportTier.STABLE,
        data_source=DataSource.UNOFFICIAL_API,
        windows=[
            LimitWindow(
                window_id=f"{provider_id}:weekly",
                name="weekly",
                quota_state=QuotaState.METERED,
                used_pct=42,
                resets_at=now + timedelta(days=2),
            )
        ],
        fetched_at=now,
        last_success_at=now,
        stale_after=now + timedelta(minutes=30),
    )


def test_failed_poll_retains_last_known_good(tmp_path: Path) -> None:
    write_snapshot(tmp_path, StateSnapshot(providers=[previous()]))
    service = QuotaService(AppConfig(), state_dir=tmp_path, adapters=[Failing("provider")])
    snapshot = asyncio.run(service.poll())
    result = snapshot.providers[0]
    assert result.fetch_status == "stale"
    assert result.windows[0].used_pct == 42
    assert result.fetch_error and result.fetch_error.retryable


def test_demo_api_and_dashboard_are_local() -> None:
    client = TestClient(create_app(AppConfig(), demo=True))
    status = client.get("/api/v1/status")
    assert status.status_code == 200
    assert status.json()["advisor"]["suggestion"]
    page = client.get("/")
    assert page.status_code == 200
    assert "Content-Security-Policy" in page.headers
    assert "https://" not in page.text


def test_bearer_auth_protects_state() -> None:
    config = AppConfig.model_validate({"server": {"auth_token": "test-secret"}})
    client = TestClient(create_app(config, demo=True))
    assert client.get("/api/v1/status").status_code == 401
    response = client.get("/api/v1/status", headers={"Authorization": "Bearer test-secret"})
    assert response.status_code == 200


def test_history_path_is_empty_before_db_exists(tmp_path: Path) -> None:
    service = QuotaService(AppConfig(), state_dir=tmp_path, adapters=[])
    assert service.history("missing") == []

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from quotacompass.core.config import AppConfig
from quotacompass.core.service import QuotaService
from quotacompass.server.app import create_app


def windows() -> list[dict]:
    return [
        {
            "name": "weekly",
            "quota_state": "metered",
            "used_pct": 44.5,
            "resets_at": "2026-07-17T00:00:00Z",
            "estimated": True,
        }
    ]


def test_manual_entry_persists_and_survives_service_restart(tmp_path: Path) -> None:
    service = QuotaService(AppConfig(), state_dir=tmp_path, adapters=[])
    snapshot = asyncio.run(service.set_manual("custom-provider", windows()))
    assert snapshot.providers[0].windows[0].used_pct == 44.5

    restarted = QuotaService(AppConfig(), state_dir=tmp_path, adapters=[])
    assert restarted.manual_entries.load()["custom-provider"][0]["used_pct"] == 44.5
    assert restarted.current() == snapshot


def test_manual_api_updates_snapshot(tmp_path: Path) -> None:
    service = QuotaService(AppConfig(), state_dir=tmp_path, adapters=[])
    with TestClient(create_app(AppConfig(), service=service)) as client:
        response = client.post(
            "/api/v1/providers/custom-provider/manual", json={"windows": windows()}
        )
        assert response.status_code == 200
        assert response.json()["providers"][0]["data_source"] == "manual"
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        assert status.json()["providers"][0]["windows"][0]["used_pct"] == 44.5

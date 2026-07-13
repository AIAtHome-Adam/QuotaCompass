from pathlib import Path

from fastapi.testclient import TestClient

from quotacompass.core.config import AppConfig
from quotacompass.core.service import QuotaService
from quotacompass.server.app import create_app


def test_manual_api_returns_422_for_invalid_cadence(tmp_path: Path) -> None:
    config = AppConfig()
    service = QuotaService(config, state_dir=tmp_path, adapters=[])
    client = TestClient(create_app(config, service=service))

    response = client.post(
        "/api/v1/providers/custom/manual",
        json={
            "windows": [
                {
                    "name": "weekly",
                    "quota_state": "metered",
                    "used_pct": 25,
                    "cadence": "whenever",
                    "timezone": "UTC",
                }
            ]
        },
    )

    assert response.status_code == 422
    assert "cadence" in response.json()["detail"]

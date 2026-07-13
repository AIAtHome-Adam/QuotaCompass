from fastapi.testclient import TestClient

from quotacompass.core.config import AppConfig
from quotacompass.server.app import create_app


def test_suggest_api_accepts_task_hint() -> None:
    config = AppConfig.model_validate(
        {"advisor": {"task_weights": {"agentic": {"claude-pro": 0.1, "codex": 1.0}}}}
    )
    client = TestClient(create_app(config, demo=True))

    response = client.get("/api/v1/suggest?task=agentic")

    assert response.status_code == 200
    assert any(item["breakdown"]["capability"] != 1 for item in response.json()["ranking"])


def test_history_api_filters_window_by_name() -> None:
    client = TestClient(create_app(AppConfig(), demo=True))

    response = client.get("/api/v1/providers/claude-pro/history?days=3&window=weekly")

    assert response.status_code == 200
    assert response.json()
    assert all(
        all(window["name"] == "weekly" for window in item["windows"]) for item in response.json()
    )


def test_demo_covers_large_provider_and_edge_state_matrix() -> None:
    client = TestClient(create_app(AppConfig(), demo=True))

    response = client.get("/api/v1/status")

    assert response.status_code == 200
    providers = response.json()["providers"]
    assert len(providers) == 10
    assert {"ok", "stale", "error"} <= {item["fetch_status"] for item in providers}
    assert {"ok", "expired", "expiring_soon", "unknown"} <= {
        item["auth"]["status"] for item in providers
    }
    assert {"metered", "unlimited", "unknown", "unavailable"} <= {
        window["quota_state"] for item in providers for window in item["windows"]
    }
    resets = [
        window["resets_at"]
        for item in providers
        for window in item["windows"]
        if window["resets_at"] is not None
    ]
    assert len(resets) > len(set(resets))


def test_demo_history_contains_inferable_reset_boundaries() -> None:
    client = TestClient(create_app(AppConfig(), demo=True))

    response = client.get("/api/v1/providers/claude-pro/history?days=12")

    assert response.status_code == 200
    values = [
        next(window["used_pct"] for window in item["windows"] if window["used_pct"] is not None)
        for item in response.json()
    ]
    assert any(previous - current >= 5 for previous, current in zip(values, values[1:], strict=False))

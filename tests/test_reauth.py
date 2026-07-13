import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from quotacompass.core.config import AppConfig
from quotacompass.core.reauth import ReauthManager
from quotacompass.server.app import create_app


def claude_config(*, trigger: str = "local") -> AppConfig:
    return AppConfig.model_validate(
        {
            "security": {"reauth_trigger": trigger},
            "providers": {"claude": {"adapter": "claude_oauth"}},
        }
    )


def test_reauth_manager_launches_fixed_helper_and_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched: list[list[str]] = []

    def fake_popen(command: list[str], **_kwargs: object) -> SimpleNamespace:
        launched.append(command)
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr("quotacompass.core.reauth.subprocess.Popen", fake_popen)
    manager = ReauthManager(claude_config(), tmp_path, cooldown_seconds=60)

    result = manager.start("claude", origin="test")

    assert result["status"] == "started"
    assert result["pid"] == 4321
    assert launched and launched[0][-1].endswith("claude.ps1")
    events = [
        json.loads(line) for line in (tmp_path / "reauth_audit.jsonl").read_text().splitlines()
    ]
    assert events[0]["provider_id"] == "claude"
    assert events[0]["origin"] == "test"
    assert set(events[0]) == {"at", "provider_id", "origin", "result", "operation_id"}

    with pytest.raises(RuntimeError, match="cooldown"):
        manager.start("claude", origin="test")


def test_reauth_api_allows_loopback_and_maps_unknown_provider(tmp_path: Path) -> None:
    app = create_app(claude_config(), demo=True)
    app.state.reauth_manager.start = lambda provider_id, origin: {
        "operation_id": "op",
        "pid": 123,
        "status": f"started:{provider_id}:{origin}",
    }
    client = TestClient(app)

    response = client.post("/api/v1/providers/claude/reauth")

    assert response.status_code == 200
    assert response.json()["status"] == "started:claude:loopback"


def test_reauth_api_respects_off_mode() -> None:
    client = TestClient(create_app(claude_config(trigger="off"), demo=True))

    response = client.post("/api/v1/providers/claude/reauth")

    assert response.status_code == 403


def test_remote_reauth_uses_token_distinct_from_read_scope() -> None:
    config = AppConfig.model_validate(
        {
            "server": {"auth_token": "read-secret"},
            "security": {
                "reauth_trigger": "remote",
                "reauth_token": "reauth-secret",
            },
            "providers": {"claude": {"adapter": "claude_oauth"}},
        }
    )
    app = create_app(config, demo=True)
    app.state.reauth_manager.start = lambda provider_id, origin: {
        "operation_id": "op",
        "pid": 123,
        "status": f"started:{provider_id}:{origin}",
    }
    client = TestClient(app, client=("10.0.0.8", 50000))

    assert client.get("/api/v1/status").status_code == 401
    assert client.get(
        "/api/v1/status", headers={"Authorization": "Bearer read-secret"}
    ).status_code == 200
    assert client.get(
        "/api/v1/status", headers={"Authorization": "Bearer reauth-secret"}
    ).status_code == 401

    endpoint = "/api/v1/providers/claude/reauth"
    assert client.post(endpoint).status_code == 401
    assert client.post(
        endpoint, headers={"Authorization": "Bearer read-secret"}
    ).status_code == 401
    response = client.post(
        endpoint, headers={"Authorization": "Bearer reauth-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "started:claude:10.0.0.8"

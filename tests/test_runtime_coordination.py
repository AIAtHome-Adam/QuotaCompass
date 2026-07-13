import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import quotacompass.cli as cli
from quotacompass.core.config import AppConfig
from quotacompass.core.demo import demo_snapshot
from quotacompass.core.runtime import pidfile_path
from quotacompass.core.service import QuotaService
from quotacompass.server.app import create_app


def test_server_lifespan_owns_and_removes_pidfile(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"server": {"port": 54791}})
    service = QuotaService(config, state_dir=tmp_path, adapters=[])
    app = create_app(config, service=service, demo=True)

    with TestClient(app):
        payload = json.loads(pidfile_path(tmp_path).read_text(encoding="utf-8"))
        assert payload["port"] == 54791

    assert not pidfile_path(tmp_path).exists()


def test_status_uses_running_server_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = demo_snapshot().model_dump(mode="json")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "load_config", lambda _path: AppConfig())
    monkeypatch.setattr(cli, "resolved_state_dir", lambda _config: tmp_path)
    monkeypatch.setattr(cli, "server_runtime", lambda _state: {"pid": 1})

    def request(_runtime: object, path: str, _config: object, *, method: str = "GET") -> object:
        calls.append((path, method))
        return snapshot

    monkeypatch.setattr(cli, "request_server", request)

    with pytest.raises(SystemExit):
        cli.main(["status", "--json"])

    assert calls == [("/api/v1/status", "GET")]
    assert json.loads(capsys.readouterr().out)["schema_version"] == 1


def test_status_poll_routes_refresh_through_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = demo_snapshot().model_dump(mode="json")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "load_config", lambda _path: AppConfig())
    monkeypatch.setattr(cli, "resolved_state_dir", lambda _config: tmp_path)
    monkeypatch.setattr(cli, "server_runtime", lambda _state: {"pid": 1})

    def request(_runtime: object, path: str, _config: object, *, method: str = "GET") -> object:
        calls.append((path, method))
        return snapshot

    monkeypatch.setattr(cli, "request_server", request)

    with pytest.raises(SystemExit):
        cli.main(["status", "--poll", "--json"])

    assert calls == [("/api/v1/poll", "POST")]

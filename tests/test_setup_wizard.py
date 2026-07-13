from pathlib import Path

import yaml

import quotacompass.setup_wizard as wizard
from quotacompass.core.discovery import CredentialCandidate


def test_proposal_combines_opencode_paths_and_separates_wsl(monkeypatch, tmp_path: Path) -> None:
    native_claude = tmp_path / ".claude" / ".credentials.json"
    wsl_codex = Path("//wsl.localhost/Ubuntu/home/user/.codex/auth.json")
    opencode_db = Path("//wsl.localhost/Ubuntu/home/user/.local/share/opencode/opencode.db")
    candidates = [
        CredentialCandidate("claude_oauth", native_claude, True),
        CredentialCandidate("codex_oauth", wsl_codex, True, environment="wsl:Ubuntu"),
        CredentialCandidate("opencode_db", opencode_db, True, environment="wsl:Ubuntu"),
    ]
    monkeypatch.setattr(wizard, "credential_candidates", lambda: candidates)
    monkeypatch.setattr(wizard, "listening_ports_by_environment", lambda: {"native": ()})
    monkeypatch.setattr(wizard, "suggest_port", lambda *_: 4888)
    proposal = wizard.build_proposal(config_path=tmp_path / "config.yaml")
    assert proposal.config.server.port == 4888
    assert "claude-pro" in proposal.config.providers
    assert "codex-wsl-ubuntu" in proposal.config.providers
    assert "opencode-wsl-ubuntu" in proposal.config.providers
    assert proposal.config.providers["opencode-wsl-ubuntu"].model_extra["state_db"]
    assert proposal.integrations == ()


def test_proposal_guides_detected_agent_integrations(monkeypatch, tmp_path: Path) -> None:
    hermes = Path("//wsl.localhost/Ubuntu/home/user/.hermes")
    openclaw = Path("//wsl.localhost/Ubuntu/home/user/.openclaw")
    candidates = [
        CredentialCandidate("hermes", hermes, True, environment="wsl:Ubuntu"),
        CredentialCandidate("openclaw", openclaw, True, environment="wsl:Ubuntu"),
    ]
    monkeypatch.setattr(wizard, "credential_candidates", lambda: candidates)
    monkeypatch.setattr(wizard, "listening_ports_by_environment", lambda: {"native": ()})
    monkeypatch.setattr(wizard, "suggest_port", lambda *_: 4888)
    monkeypatch.setattr(
        wizard,
        "_skill_source_path",
        lambda target: tmp_path / "agent-skills" / target / "quotacompass",
    )

    proposal = wizard.build_proposal(config_path=tmp_path / "config.yaml")
    integrations = {item["target"]: item for item in proposal.as_dict()["integrations"]}

    assert "nous-wsl-ubuntu" in proposal.config.providers
    assert "openclaw-wsl-ubuntu" not in proposal.config.providers
    assert integrations["hermes"]["development_install"]["method"] == "copy_directory"
    assert integrations["hermes"]["development_install"]["destination"].endswith(
        ".hermes\\skills\\quotacompass"
    ) or integrations["hermes"]["development_install"]["destination"].endswith(
        ".hermes/skills/quotacompass"
    )
    assert integrations["hermes"]["published_install_command"].startswith("hermes skills install")
    assert "openclaw skills install" in integrations["openclaw"]["development_install"]["command"]
    assert integrations["openclaw"]["published_install_command"].startswith(
        "openclaw skills install"
    )
    assert integrations["hermes"]["config"]["quotacompass.url"] == ("http://<windows-host-ip>:4888")
    assert integrations["openclaw"]["config"][
        "skills.entries.quotacompass.config.state_file"
    ].endswith("current.json")
    assert "Integration commands are guidance only" in " ".join(proposal.notes)


def test_proposal_reports_and_blocks_native_wsl_and_reserved_ports(
    monkeypatch, tmp_path: Path
) -> None:
    captured = {}

    def suggest(host, start, blocked):
        captured.update(host=host, start=start, blocked=set(blocked))
        return 4748

    monkeypatch.setattr(wizard, "credential_candidates", lambda: [])
    monkeypatch.setattr(
        wizard,
        "listening_ports_by_environment",
        lambda: {"native": (3000, 4747), "wsl:Ubuntu": (9119,)},
    )
    monkeypatch.setattr(wizard, "suggest_port", suggest)
    proposal = wizard.build_proposal(config_path=tmp_path / "config.yaml", reserved_ports={18789})
    payload = proposal.as_dict()

    assert captured == {
        "host": "127.0.0.1",
        "start": 4747,
        "blocked": {3000, 4747, 9119, 18789},
    }
    assert proposal.config.reserved_ports == [18789]
    assert payload["suggested_port"] == 4748
    assert payload["ports_in_use"] == {
        "native": [3000, 4747],
        "wsl:Ubuntu": [9119],
    }
    assert payload["runtime"]["dashboard_url"] == "http://127.0.0.1:4748/"
    assert payload["runtime"]["status_endpoint"].endswith("/api/v1/status")
    assert payload["runtime"]["state_file"].endswith("current.json")


def test_write_proposal_is_valid_and_refuses_overwrite(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wizard, "credential_candidates", lambda: [])
    monkeypatch.setattr(wizard, "listening_ports_by_environment", lambda: {"native": ()})
    monkeypatch.setattr(wizard, "suggest_port", lambda *_: 4747)
    proposal = wizard.build_proposal(config_path=tmp_path / "config.yaml")
    path = wizard.write_proposal(proposal)
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["server"]["port"] == 4747
    try:
        wizard.write_proposal(proposal)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing config must not be overwritten without --force")


def test_proposal_emits_reviewable_service_commands(monkeypatch, tmp_path: Path) -> None:
    installer = tmp_path / "install-service.ps1"
    installer.write_text("# staged installer", encoding="utf-8")
    monkeypatch.setattr(wizard, "credential_candidates", lambda: [])
    monkeypatch.setattr(wizard, "listening_ports_by_environment", lambda: {"native": ()})
    monkeypatch.setattr(wizard, "suggest_port", lambda *_: 4747)
    monkeypatch.setattr(wizard, "_service_platform", lambda: "windows")
    monkeypatch.setattr(wizard, "_service_script_path", lambda _platform: installer)
    monkeypatch.setattr(wizard.shutil, "which", lambda _command: r"C:\Tools\quotacompass.exe")

    config_path = tmp_path / "config with spaces.yaml"
    payload = wizard.build_proposal(config_path=config_path).as_dict()
    service = payload["service"]

    assert service["platform"] == "windows"
    assert service["automatic"] is False
    assert service["review"]["argv"][-1] == "-WhatIf"
    assert "-WhatIf" not in service["install"]["argv"]
    assert str(config_path.resolve()) in service["install"]["argv"]
    assert service["uninstall"]["argv"][-2:] == ["-Action", "Uninstall"]
    assert "Service review/install commands are guidance only" in " ".join(payload["notes"])


def test_setup_display_redacts_read_and_reauth_tokens() -> None:
    config = wizard.AppConfig.model_validate(
        {
            "server": {"auth_token": "read-secret"},
            "security": {
                "reauth_trigger": "remote",
                "reauth_token": "reauth-secret",
            },
        }
    )

    payload = wizard._redacted_config(config)

    assert payload["server"]["auth_token"] == "<configured>"
    assert payload["security"]["reauth_token"] == "<configured>"
    assert "read-secret" not in str(payload)
    assert "reauth-secret" not in str(payload)

from __future__ import annotations

import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quotacompass.core.config import AppConfig, default_config_path, resolved_state_dir
from quotacompass.core.discovery import (
    CredentialCandidate,
    credential_candidates,
    listening_ports_by_environment,
    suggest_port,
)
from quotacompass.core.statefile import _atomic_write


def _redacted_config(config: AppConfig) -> dict[str, Any]:
    payload = config.model_dump(mode="json", exclude_none=True)
    for section, key in (("server", "auth_token"), ("security", "reauth_token")):
        values = payload.get(section)
        if isinstance(values, dict) and key in values:
            values[key] = "<configured>"
    return payload


@dataclass(frozen=True)
class SetupProposal:
    config: AppConfig
    config_path: Path
    detected: tuple[CredentialCandidate, ...]
    ports_in_use: dict[str, tuple[int, ...]]
    integrations: tuple[dict[str, Any], ...]
    service: dict[str, Any]
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        display_host = (
            "127.0.0.1" if self.config.server.host in {"0.0.0.0", "::"} else self.config.server.host
        )
        state_dir = resolved_state_dir(self.config)
        return {
            "config_path": str(self.config_path),
            "config": _redacted_config(self.config),
            "suggested_port": self.config.server.port,
            "ports_in_use": {
                environment: list(ports) for environment, ports in self.ports_in_use.items()
            },
            "runtime": {
                "dashboard_url": f"http://{display_host}:{self.config.server.port}/",
                "api_url": f"http://{display_host}:{self.config.server.port}/api/v1",
                "status_endpoint": (
                    f"http://{display_host}:{self.config.server.port}/api/v1/status"
                ),
                "state_file": str(state_dir / "current.json"),
                "markdown_state_file": str(state_dir / "current.md"),
            },
            "detected": [
                {
                    "adapter": item.adapter,
                    "path": str(item.path),
                    "environment": item.environment,
                }
                for item in self.detected
            ],
            "integrations": list(self.integrations),
            "service": self.service,
            "notes": list(self.notes),
        }


def _slug(adapter: str, environment: str, seen: dict[str, int]) -> str:
    base = {
        "claude_oauth": "claude-pro",
        "codex_oauth": "codex",
        "cursor": "cursor",
        "opencode": "opencode",
        "opencode_db": "opencode",
        "gemini": "gemini",
        "copilot": "copilot",
        "hermes": "nous",
    }.get(adapter, adapter.replace("_", "-"))
    suffix = ""
    if environment.startswith("wsl:"):
        suffix = f"-wsl-{environment.split(':', 1)[1].lower()}"
    candidate = f"{base}{suffix}"
    count = seen.get(candidate, 0)
    seen[candidate] = count + 1
    return candidate if count == 0 else f"{candidate}-{count + 1}"


def _skill_source_path(target: str) -> Path:
    packaged = Path(__file__).resolve().parent / "agent_skills" / target / "quotacompass"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[1] / "skills" / target / "quotacompass"


def _path_for_environment(path: Path, environment: str) -> str:
    value = path.resolve()
    if environment.startswith("wsl:") and value.drive:
        drive = value.drive.rstrip(":").lower()
        tail = value.as_posix().split(":/", 1)[1]
        return f"/mnt/{drive}/{tail}"
    return value.as_posix() if environment.startswith("wsl:") else str(value)


def _service_platform() -> str:
    if os.name == "nt":
        return "windows"
    return "macos" if sys.platform == "darwin" else "systemd"


def _service_script_path(platform: str) -> Path:
    filename = "install-service.ps1" if platform == "windows" else "install-service.sh"
    packaged = Path(__file__).resolve().parent / "service_scripts" / filename
    if packaged.is_file():
        return packaged
    return Path(__file__).resolve().parents[1] / "scripts" / filename


def _service_guidance(config_path: Path) -> dict[str, Any]:
    platform = _service_platform()
    script = _service_script_path(platform)
    command = shutil.which("quotacompass") or "quotacompass"
    config = str(config_path.resolve())
    if platform == "windows":
        base = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
        common = ["-Command", command, "-ConfigPath", config]
        review = base + ["-Action", "Install"] + common + ["-WhatIf"]
        install = base + ["-Action", "Install"] + common
        uninstall = base + ["-Action", "Uninstall"]
        environment: dict[str, str] = {}
    else:
        base = ["sh", str(script)]
        review = base + ["preview", config]
        install = base + ["install", config]
        uninstall = base + ["uninstall", config]
        environment = {"QUOTACOMPASS_COMMAND": command}
    return {
        "platform": platform,
        "installer_path": str(script),
        "review": {"argv": review, "environment": environment},
        "install": {"argv": install, "environment": environment},
        "uninstall": {"argv": uninstall, "environment": environment},
        "automatic": False,
        "note": "Review first; setup never creates or removes a background service.",
    }


def _integration_guidance(
    candidates: tuple[CredentialCandidate, ...], config: AppConfig
) -> tuple[dict[str, Any], ...]:
    state_file = resolved_state_dir(config) / "current.json"
    guidance: list[dict[str, Any]] = []
    for item in candidates:
        if item.adapter not in {"hermes", "openclaw"}:
            continue
        target = item.adapter
        source = _skill_source_path(target)
        source_for_environment = _path_for_environment(source, item.environment)
        state_for_environment = _path_for_environment(state_file, item.environment)
        if item.environment.startswith("wsl:"):
            url = f"http://<windows-host-ip>:{config.server.port}"
            url_hint = "Resolve <windows-host-ip> with: ip route | awk '/^default/{print $3}'"
        else:
            url = f"http://127.0.0.1:{config.server.port}"
            url_hint = "QuotaCompass binds to loopback by default."

        if target == "hermes":
            development_install: dict[str, Any] = {
                "method": "copy_directory",
                "source": str(source),
                "destination": str(item.path / "skills" / "quotacompass"),
                "reason": "Hermes 0.18 discovers local skills here; its installer accepts registries or HTTP, not local paths.",
            }
            published_command = "hermes skills install <owner/repo>"
            config_keys = {
                "quotacompass.url": url,
                "quotacompass.state_file": state_for_environment,
            }
        else:
            development_install = {
                "method": "command",
                "command": (
                    "openclaw skills install "
                    f"{shlex.quote(source_for_environment)} --as quotacompass"
                ),
            }
            published_command = "openclaw skills install <clawhub-slug>"
            config_keys = {
                "skills.entries.quotacompass.config.url": url,
                "skills.entries.quotacompass.config.state_file": state_for_environment,
            }
        guidance.append(
            {
                "target": target,
                "environment": item.environment,
                "detected_path": str(item.path),
                "skill_source": str(source),
                "development_install": development_install,
                "published_install_command": published_command,
                "config": config_keys,
                "url_hint": url_hint,
            }
        )
    return tuple(guidance)


def build_proposal(
    *,
    config_path: Path | None = None,
    host: str = "127.0.0.1",
    start_port: int = 4747,
    reserved_ports: set[int] | None = None,
) -> SetupProposal:
    candidates = tuple(item for item in credential_candidates() if item.exists)
    port_inventory = listening_ports_by_environment()
    blocked_ports = set(reserved_ports or set())
    for ports in port_inventory.values():
        blocked_ports.update(ports)
    port = suggest_port(host, start_port, blocked_ports)
    providers: dict[str, dict[str, Any]] = {}
    seen: dict[str, int] = {}
    opencode: dict[str, dict[str, str]] = {}
    for item in candidates:
        if item.adapter == "openclaw":
            continue
        if item.adapter in {"opencode", "opencode_db"}:
            entry = opencode.setdefault(item.environment, {})
            entry["credentials" if item.adapter == "opencode" else "state_db"] = str(item.path)
            continue
        provider_id = _slug(item.adapter, item.environment, seen)
        if item.adapter == "hermes":
            providers[provider_id] = {
                "adapter": "nous",
                "label": "Nous Portal",
                "credentials": str(item.path / "auth.json"),
                "support_tier": "experimental",
            }
        elif item.adapter == "cursor":
            providers[provider_id] = {
                "adapter": "cursor",
                "label": "Cursor",
                "state_db": str(item.path),
                "support_tier": "beta",
            }
        else:
            providers[provider_id] = {
                "adapter": item.adapter,
                "label": provider_id.replace("-", " ").title(),
                "credentials": str(item.path),
            }
    for environment, paths in opencode.items():
        if "state_db" not in paths:
            continue
        provider_id = _slug("opencode", environment, seen)
        providers[provider_id] = {
            "adapter": "opencode",
            "label": "OpenCode Go",
            "support_tier": "beta",
            **paths,
        }
    config = AppConfig.model_validate(
        {
            "server": {"host": host, "port": port},
            "reserved_ports": sorted(reserved_ports or set()),
            "providers": providers,
        }
    )
    integrations = _integration_guidance(candidates, config)
    service = _service_guidance(config_path or default_config_path())
    notes = [
        "Hermes/OpenClaw installs are integration targets and are not quota providers.",
        "Integration commands are guidance only; setup never installs or publishes agent skills.",
        "Detected native/WSL listener ports and user-reserved ports are excluded from the suggestion.",
        "Service review/install commands are guidance only and are never executed by setup.",
        "No credentials are copied; generated entries reference native stores in place.",
        "API-key providers are not auto-enabled unless their environment variables are configured.",
    ]
    if not providers:
        notes.append("No supported credential stores were detected; add a manual provider first.")
    return SetupProposal(
        config=config,
        config_path=config_path or default_config_path(),
        detected=candidates,
        ports_in_use=port_inventory,
        integrations=integrations,
        service=service,
        notes=tuple(notes),
    )


def write_proposal(proposal: SetupProposal, *, overwrite: bool = False) -> Path:
    path = proposal.config_path
    if path.exists() and not overwrite:
        raise FileExistsError(f"Configuration already exists: {path}")
    payload = proposal.config.model_dump(mode="json", exclude_none=True)
    _atomic_write(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    return path

from __future__ import annotations

import os
import re
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import psutil


@dataclass(frozen=True)
class CredentialCandidate:
    adapter: str
    path: Path
    exists: bool
    source: str = "well_known"
    environment: str = "native"


def home() -> Path:
    return Path.home()


def _decode_wsl_output(data: bytes) -> str:
    if b"\x00" in data:
        return data.decode("utf-16-le", errors="replace").lstrip("\ufeff")
    return data.decode(errors="replace").lstrip("\ufeff")


def wsl_distros() -> list[str]:
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [
        line.strip().lstrip("*").strip()
        for line in _decode_wsl_output(result.stdout).splitlines()
        if line.strip()
    ]


def wsl_home(distro: str) -> str | None:
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "sh", "-lc", 'printf %s "$HOME"'],
            check=True,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = _decode_wsl_output(result.stdout).strip()
    return value if value.startswith("/") else None


def wsl_unc_path(distro: str, linux_path: str) -> Path:
    parts = PurePosixPath(linux_path).parts[1:]
    return Path("//wsl.localhost") / distro / Path(*parts)


def native_listening_ports() -> set[int]:
    ports: set[int] = set()
    try:
        connections = psutil.net_connections(kind="tcp")
    except (OSError, psutil.Error):
        return ports
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN or not connection.laddr:
            continue
        try:
            port = int(connection.laddr.port)
        except AttributeError:
            port = int(connection.laddr[1])
        if 1 <= port <= 65535:
            ports.add(port)
    return ports


def _parse_ss_listening_ports(output: str) -> set[int]:
    ports: set[int] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        match = re.search(r":(\d+)$", parts[3])
        if match:
            ports.add(int(match.group(1)))
    return ports


def wsl_listening_ports(distro: str) -> set[int]:
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "ss", "-H", "-ltn"],
            check=True,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return _parse_ss_listening_ports(_decode_wsl_output(result.stdout))


def listening_ports_by_environment(*, include_wsl: bool = True) -> dict[str, tuple[int, ...]]:
    inventory = {"native": tuple(sorted(native_listening_ports()))}
    if include_wsl and os.name == "nt":
        for distro in wsl_distros():
            inventory[f"wsl:{distro}"] = tuple(sorted(wsl_listening_ports(distro)))
    return inventory


def credential_candidates(*, include_wsl: bool = True) -> list[CredentialCandidate]:
    user_home = home()
    paths = {
        "claude_oauth": user_home / ".claude" / ".credentials.json",
        "codex_oauth": user_home / ".codex" / "auth.json",
        "opencode": user_home / ".local" / "share" / "opencode" / "auth.json",
        "gemini": user_home / ".gemini" / "oauth_creds.json",
        "copilot": user_home / ".config" / "github-copilot" / "apps.json",
    }
    if os.name == "nt" and os.getenv("APPDATA"):
        paths["cursor"] = (
            Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
        )
    candidates = [
        CredentialCandidate(adapter, path, path.exists()) for adapter, path in paths.items()
    ]
    if include_wsl and os.name == "nt":
        relative = {
            "claude_oauth": ".claude/.credentials.json",
            "codex_oauth": ".codex/auth.json",
            "opencode": ".local/share/opencode/auth.json",
            "opencode_db": ".local/share/opencode/opencode.db",
            "gemini": ".gemini/oauth_creds.json",
            "hermes": ".hermes",
            "openclaw": ".openclaw",
        }
        for distro in wsl_distros():
            linux_home = wsl_home(distro)
            if not linux_home:
                continue
            home_path = wsl_unc_path(distro, linux_home)
            for adapter, suffix in relative.items():
                path = home_path / Path(*PurePosixPath(suffix).parts)
                candidates.append(
                    CredentialCandidate(
                        adapter,
                        path,
                        path.exists(),
                        source="wsl_probe",
                        environment=f"wsl:{distro}",
                    )
                )
    return candidates


def port_is_free(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def suggest_port(
    host: str = "127.0.0.1", start: int = 4747, reserved: set[int] | None = None
) -> int:
    blocked = reserved or set()
    for port in range(start, 65536):
        if port not in blocked and port_is_free(host, port):
            return port
    raise RuntimeError("no free TCP port found")

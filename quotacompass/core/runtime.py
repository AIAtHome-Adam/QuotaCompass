from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quotacompass.core.config import AppConfig
from quotacompass.core.statefile import _atomic_write

PIDFILE = "server.json"


def pidfile_path(state_dir: Path) -> Path:
    return state_dir / PIDFILE


def write_pidfile(state_dir: Path, host: str, port: int) -> Path:
    existing = server_runtime(state_dir)
    if existing and existing["pid"] != os.getpid():
        raise RuntimeError(
            f"QuotaCompass server already runs as PID {existing['pid']} on "
            f"{existing['host']}:{existing['port']}"
        )
    path = pidfile_path(state_dir)
    payload = {
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "started_at": datetime.now(UTC).isoformat(),
    }
    _atomic_write(path, json.dumps(payload, separators=(",", ":")) + "\n")
    return path


def remove_pidfile(state_dir: Path) -> None:
    path = pidfile_path(state_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if int(payload.get("pid", -1)) == os.getpid():
            path.unlink(missing_ok=True)
    except (OSError, ValueError, json.JSONDecodeError):
        return


def read_pidfile(state_dir: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(pidfile_path(state_dir).read_text(encoding="utf-8"))
        return {
            "pid": int(payload["pid"]),
            "host": str(payload["host"]),
            "port": int(payload["port"]),
            "started_at": str(payload["started_at"]),
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def server_runtime(state_dir: Path, *, timeout: float = 0.35) -> dict[str, Any] | None:
    runtime = read_pidfile(state_dir)
    if runtime is None or not _pid_exists(runtime["pid"]):
        return None
    try:
        with socket.create_connection((runtime["host"], runtime["port"]), timeout=timeout):
            return runtime
    except OSError:
        return None


def request_server(
    runtime: dict[str, Any],
    path: str,
    config: AppConfig,
    *,
    method: str = "GET",
    timeout: float = 20,
) -> object:
    host = runtime["host"]
    if host == "0.0.0.0":
        host = "127.0.0.1"
    elif host == "::":
        host = "::1"
    authority = f"[{host}]" if ":" in host and not host.startswith("[") else host
    request = urllib.request.Request(
        f"http://{authority}:{runtime['port']}{path}",
        method=method,
        headers={"Accept": "application/json"},
    )
    if config.server.auth_token:
        request.add_header("Authorization", f"Bearer {config.server.auth_token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QuotaCompass server returned HTTP {exc.code}: {detail}") from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"QuotaCompass server request failed: {exc}") from exc

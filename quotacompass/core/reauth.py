from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from quotacompass.core.config import AppConfig
from quotacompass.core.statefile import _atomic_write

SCRIPT_NAMES = {
    "claude_oauth": "claude",
    "codex_oauth": "codex",
    "opencode": "opencode",
    "copilot": "copilot",
    "gemini": "gemini",
    "nous": "nous",
}


class ReauthManager:
    def __init__(self, config: AppConfig, state_dir: Path, *, cooldown_seconds: int = 60) -> None:
        self.config = config
        self.state_dir = state_dir
        self.cooldown_seconds = cooldown_seconds
        self._last_start: dict[str, float] = {}

    def _script(self, provider_id: str) -> Path:
        provider = self.config.providers.get(provider_id)
        if provider is None:
            raise KeyError(f"Unknown configured provider: {provider_id}")
        name = SCRIPT_NAMES.get(provider.adapter)
        if not name:
            raise ValueError(f"Provider {provider_id} has no guided reauthentication helper")
        suffix = "ps1" if os.name == "nt" else "sh"
        packaged = Path(__file__).parents[1] / "reauth_scripts" / f"{name}.{suffix}"
        development = Path(__file__).parents[2] / "scripts" / "reauth" / f"{name}.{suffix}"
        script = packaged if packaged.is_file() else development
        resolved = script.resolve(strict=True)
        allowed_roots = {
            packaged.parent.resolve(),
            development.parent.resolve(),
        }
        if resolved.parent not in allowed_roots or resolved.is_symlink():
            raise ValueError("Reauthentication helper failed the fixed-path safety check")
        return resolved

    def _audit(self, provider_id: str, origin: str, result: str, operation_id: str) -> None:
        path = self.state_dir / "reauth_audit.jsonl"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        event = {
            "at": datetime.now(UTC).isoformat(),
            "provider_id": provider_id,
            "origin": origin,
            "result": result,
            "operation_id": operation_id,
        }
        _atomic_write(path, existing + json.dumps(event, separators=(",", ":")) + "\n")

    def start(self, provider_id: str, *, origin: str) -> dict[str, str | int]:
        now = time.monotonic()
        last = self._last_start.get(provider_id)
        if last is not None and now - last < self.cooldown_seconds:
            remaining = max(1, round(self.cooldown_seconds - (now - last)))
            raise RuntimeError(f"Reauthentication cooldown active for {remaining}s")
        script = self._script(provider_id)
        operation_id = uuid.uuid4().hex
        command = (
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "RemoteSigned",
                "-File",
                str(script),
            ]
            if os.name == "nt"
            else ["sh", str(script)]
        )
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=flags,
            )
        except OSError:
            self._audit(provider_id, origin, "launch_failed", operation_id)
            raise
        self._last_start[provider_id] = now
        self._audit(provider_id, origin, "started", operation_id)
        return {"operation_id": operation_id, "pid": process.pid, "status": "started"}

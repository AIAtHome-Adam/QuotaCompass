from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from quotacompass.core.models import AuthState, StateSnapshot


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def render_markdown(snapshot: StateSnapshot) -> str:
    lines = [
        "# QuotaCompass status",
        "",
        f"Generated: {snapshot.generated_at.isoformat()}",
        "",
        "| Provider | Window | Available | Reset | Health |",
        "|---|---|---:|---|---|",
    ]
    for provider in snapshot.providers:
        for notice in provider.capacity_notices:
            lines.append(f"> **{provider.label}: {notice.title}.** {notice.message}")
            lines.append("")
        if not provider.windows:
            lines.append(
                f"| {provider.label} | — | Unknown | — | {provider.fetch_status.value} |"
            )
        for window in provider.windows:
            available = (
                f"{100 - window.used_pct:.0f}%"
                if window.used_pct is not None
                else window.quota_state.value.title()
            )
            reset = window.resets_at.isoformat() if window.resets_at else "—"
            lines.append(
                f"| {provider.label} | {window.name} | {available} | {reset} | "
                f"{provider.fetch_status.value} |"
            )
    auth_attention = [
        provider
        for provider in snapshot.providers
        if provider.auth.status
        in {AuthState.EXPIRING_SOON, AuthState.EXPIRED, AuthState.ERROR}
    ]
    if auth_attention:
        lines.extend(["", "## Authentication attention", ""])
        for provider in auth_attention:
            expiry = (
                f"; expires {provider.auth.expires_at.isoformat()}"
                if provider.auth.expires_at
                else ""
            )
            action = (
                f"; run {provider.auth.reauth.command}"
                if provider.auth.reauth and provider.auth.reauth.command
                else ""
            )
            lines.append(
                f"- **{provider.label}:** {provider.auth.status.value.replace('_', ' ')}"
                f"{expiry}{action}"
            )
    if snapshot.advisor.suggestion:
        lines.extend(["", f"**Suggested provider:** `{snapshot.advisor.suggestion}`"])
    if snapshot.advisor.expiring_unused:
        lines.extend(["", "## Expiring unused quota", ""])
        lines.extend(f"- {item.note}" for item in snapshot.advisor.expiring_unused)
    return "\n".join(lines) + "\n"


def write_snapshot(directory: Path, snapshot: StateSnapshot) -> tuple[Path, Path]:
    json_path = directory / "current.json"
    markdown_path = directory / "current.md"
    payload = snapshot.model_dump(mode="json")
    _atomic_write(json_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    _atomic_write(markdown_path, render_markdown(snapshot))
    return json_path, markdown_path


def read_snapshot(directory: Path) -> StateSnapshot | None:
    path = directory / "current.json"
    if not path.exists():
        return None
    return StateSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

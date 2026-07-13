from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quotacompass.core.statefile import _atomic_write


class ManualEntryStore:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "manual_entries.json"

    def load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        if not isinstance(value, dict):
            return {}
        return {
            str(provider_id): windows
            for provider_id, windows in value.items()
            if isinstance(windows, list)
        }

    def set(self, provider_id: str, windows: list[dict[str, Any]]) -> None:
        entries = self.load()
        entries[provider_id] = windows
        _atomic_write(
            self.path,
            json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        )

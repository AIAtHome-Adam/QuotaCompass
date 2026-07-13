"""Development helper: print Cursor credential shapes only, never values."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path


def shape(value: str) -> object:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return {"json_keys": sorted(parsed)}
    except json.JSONDecodeError:
        pass
    if value.count(".") == 2:
        try:
            part = value.split(".")[1]
            payload = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            return {"jwt_claim_keys": sorted(payload)}
        except (ValueError, json.JSONDecodeError):
            pass
    return {"type": "opaque_string"}


def main() -> None:
    path = Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT key, value FROM ItemTable WHERE key IN "
            "('cursorAuth/accessToken', 'cursorAuth/cachedScopedProfile')"
        ).fetchall()
        for key, value in rows:
            print(f"{key}: {shape(value)}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

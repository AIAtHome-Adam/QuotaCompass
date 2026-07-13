"""Development spike: show Cursor usage response structure without identity/token strings."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path

import httpx


def sanitize(value: object) -> object:
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}>"


def main() -> None:
    path = Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        token = connection.execute(
            "SELECT value FROM ItemTable WHERE key='cursorAuth/accessToken'"
        ).fetchone()[0]
    finally:
        connection.close()
    part = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    user_id = claims["sub"]
    response = httpx.get(
        "https://cursor.com/api/usage-summary",
        headers={
            "Cookie": f"WorkosCursorSessionToken={user_id}%3A%3A{token}",
            "Referer": "https://www.cursor.com/settings",
        },
        timeout=15,
    )
    print(f"status={response.status_code}")
    if response.headers.get("content-type", "").startswith("application/json"):
        print(json.dumps(sanitize(response.json()), indent=2))


if __name__ == "__main__":
    main()

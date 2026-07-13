"""Development helper: print Cursor auth key names only, never values."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def main() -> None:
    path = Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        keys = connection.execute(
            "SELECT key FROM ItemTable WHERE key LIKE 'cursorAuth/%' ORDER BY key"
        ).fetchall()
        print("\n".join(key for (key,) in keys))
    finally:
        connection.close()


if __name__ == "__main__":
    main()

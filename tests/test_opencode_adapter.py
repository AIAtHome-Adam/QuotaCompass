import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotacompass.adapters.opencode import OpenCodeAdapter


def test_opencode_sums_local_message_costs(tmp_path: Path) -> None:
    database = tmp_path / "opencode.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE message (id TEXT PRIMARY KEY, data TEXT)")
    now = datetime.now(UTC)
    rows = [
        {
            "cost": 3.0,
            "time": {"created": int((now - timedelta(hours=1)).timestamp() * 1000)},
        },
        {
            "cost": 6.0,
            "time": {"created": int((now - timedelta(days=2)).timestamp() * 1000)},
        },
        {
            "cost": 20.0,
            "time": {"created": int((now - timedelta(days=20)).timestamp() * 1000)},
        },
    ]
    connection.executemany(
        "INSERT INTO message VALUES (?, ?)",
        [(str(index), json.dumps(row)) for index, row in enumerate(rows)],
    )
    connection.commit()
    connection.close()

    result = asyncio.run(
        OpenCodeAdapter(
            "opencode",
            {"state_db": str(database), "credentials": str(tmp_path / "auth.json")},
        ).fetch_usage()
    )
    by_name = {window.name: window for window in result.windows}
    assert by_name["5h"].used_pct == 25
    assert by_name["weekly"].used_pct == 30
    assert round(by_name["monthly"].used_pct or 0, 2) == 48.33
    assert all(window.estimated for window in result.windows)
    assert result.data_source == "local_derived"

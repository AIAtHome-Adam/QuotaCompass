import asyncio
import base64
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from quotacompass.adapters.cursor import CursorAdapter


def jwt() -> str:
    claims = {
        "sub": "fixture-user",
        "exp": int((datetime.now(UTC) + timedelta(days=10)).timestamp()),
    }
    part = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{part}.signature"


def state_db(path: Path, token: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute("INSERT INTO ItemTable VALUES ('cursorAuth/accessToken', ?)", (token,))
    connection.commit()
    connection.close()


def test_cursor_normalizes_billing_cycle(tmp_path: Path) -> None:
    token = jwt()
    database = tmp_path / "state.vscdb"
    state_db(database, token)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "fixture-user%3A%3A" in request.headers["cookie"]
        return httpx.Response(
            200,
            json={
                "billingCycleEnd": "2026-08-01T00:00:00Z",
                "membershipType": "pro",
                "isUnlimited": False,
                "individualUsage": {
                    "plan": {
                        "used": 2000,
                        "limit": 5648,
                        "remaining": 3648,
                        "totalPercentUsed": 35.41,
                    }
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CursorAdapter("cursor", {"state_db": str(database)}, client=client)
    result = asyncio.run(adapter.fetch_usage())
    asyncio.run(client.aclose())
    assert result.windows[0].name == "monthly"
    assert result.windows[0].used_pct == 35.41
    assert result.support_tier == "beta"
    assert token not in result.model_dump_json()

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from quotacompass.adapters.claude_oauth import ClaudeOAuthAdapter
from quotacompass.adapters.codex_oauth import CodexOAuthAdapter


def future_timestamp() -> int:
    return int((datetime.now(UTC) + timedelta(days=30)).timestamp())


def unsigned_jwt(exp: int) -> str:
    import base64

    payload = (
        base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    )
    return f"x.{payload}.x"


def test_claude_fixture_normalizes_windows(tmp_path: Path) -> None:
    credentials = tmp_path / "claude.json"
    credentials.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "secret-test-token",
                    "expiresAt": future_timestamp() * 1000,
                    "subscriptionType": "max",
                }
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-test-token"
        return httpx.Response(
            200,
            json={
                "five_hour": {"utilization": 12, "resets_at": "2026-07-11T00:00:00Z"},
                "seven_day": {"utilization": 34, "resets_at": "2026-07-17T00:00:00Z"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ClaudeOAuthAdapter(
        "claude", {"credentials": str(credentials)}, client=client
    )
    status = asyncio.run(adapter.fetch_usage())
    asyncio.run(client.aclose())
    assert [(item.name, item.used_pct) for item in status.windows] == [
        ("5h", 12),
        ("weekly", 34),
    ]
    assert "secret-test-token" not in status.model_dump_json()


def test_codex_classifies_by_duration_not_slot(tmp_path: Path) -> None:
    credentials = tmp_path / "codex.json"
    credentials.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": unsigned_jwt(future_timestamp()),
                    "account_id": "account-123456789",
                }
            }
        ),
        encoding="utf-8",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "rate_limit": {
                    "primary_window": {
                        "limit_window_seconds": 604800,
                        "used_percent": 40,
                        "reset_at": 1784000000,
                    },
                    "secondary_window": {
                        "limit_window_seconds": 18000,
                        "used_percent": 20,
                        "reset_at": 1783900000,
                    },
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CodexOAuthAdapter(
        "codex", {"credentials": str(credentials)}, client=client
    )
    status = asyncio.run(adapter.fetch_usage())
    asyncio.run(client.aclose())
    assert [(item.name, item.used_pct) for item in status.windows] == [
        ("weekly", 40),
        ("5h", 20),
    ]
    assert status.account_hint == "…456789"


def test_codex_detects_explicit_weekly_only_capacity_boost() -> None:
    payload = {
        "rate_limit": {
            "primary_window": {
                "limit_window_seconds": 604800,
                "used_percent": 7,
                "reset_at": 1784489208,
            },
            "secondary_window": None,
        }
    }

    windows, notices = CodexOAuthAdapter._windows(payload, "codex")

    assert [(window.name, window.quota_state) for window in windows] == [
        ("5h", "unlimited"),
        ("weekly", "metered"),
    ]
    assert windows[0].temporary is True
    assert windows[0].inferred is True
    assert notices[0].kind == "promotion"
    assert "weekly limit still applies" in notices[0].message
    assert notices[0].evidence == (
        "valid_weekly_window_with_explicitly_null_secondary_window"
    )


def test_codex_does_not_infer_boost_from_missing_secondary_field() -> None:
    payload = {
        "rate_limit": {
            "primary_window": {
                "limit_window_seconds": 604800,
                "used_percent": 7,
                "reset_at": 1784489208,
            }
        }
    }

    windows, notices = CodexOAuthAdapter._windows(payload, "codex")

    assert [window.name for window in windows] == ["weekly"]
    assert notices == []

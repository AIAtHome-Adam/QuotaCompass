import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from quotacompass.adapters.nous import NousAdapter


def test_nous_maps_subscription_credits(tmp_path: Path) -> None:
    credentials = tmp_path / "auth.json"
    credentials.write_text(
        json.dumps(
            {
                "providers": {
                    "nous": {
                        "access_token": "fixture-secret",
                        "portal_base_url": "https://portal.nousresearch.com",
                        "expires_at": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fixture-secret"
        return httpx.Response(
            200,
            json={
                "subscription": {
                    "plan": "Pro",
                    "monthly_credits": 100,
                    "credits_remaining": 65,
                    "current_period_end": "2026-08-01T00:00:00Z",
                },
                "paid_service_access": {
                    "allowed": True,
                    "total_usable_credits": 75,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = NousAdapter("nous", {"credentials": str(credentials)}, client=client)
    result = asyncio.run(adapter.fetch_usage())
    asyncio.run(client.aclose())
    assert result.windows[0].used_pct == 35
    assert result.windows[0].resets_at is not None
    assert result.raw_extras["total_usable_credits"] == 75
    assert "fixture-secret" not in result.model_dump_json()


def test_nous_rollover_does_not_report_misleading_percentage(tmp_path: Path) -> None:
    credentials = tmp_path / "auth.json"
    credentials.write_text(
        json.dumps(
            {
                "providers": {
                    "nous": {
                        "access_token": "secret",
                        "expires_at": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "subscription": {"monthly_credits": 100, "credits_remaining": 125},
                "paid_service_access": {"allowed": True},
            },
        )
    )
    client = httpx.AsyncClient(transport=transport)
    result = asyncio.run(
        NousAdapter("nous", {"credentials": str(credentials)}, client=client).fetch_usage()
    )
    asyncio.run(client.aclose())
    assert result.windows[0].quota_state == "unknown"
    assert result.windows[0].used_pct is None

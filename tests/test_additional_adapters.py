import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from quotacompass.adapters.anthropic_api import AnthropicAPIAdapter
from quotacompass.adapters.copilot import CopilotAdapter
from quotacompass.adapters.gemini import GeminiAdapter
from quotacompass.adapters.xai import XAIAdapter


def test_anthropic_admin_aggregates_official_usage(monkeypatch) -> None:
    monkeypatch.setenv("TEST_ANTHROPIC_ADMIN", "admin-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "admin-secret"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "results": [
                            {"uncached_input_tokens": 100, "output_tokens": 20},
                            {"uncached_input_tokens": 50, "output_tokens": 10},
                        ]
                    }
                ],
                "has_more": False,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AnthropicAPIAdapter(
        "anthropic", {"admin_key_env": "TEST_ANTHROPIC_ADMIN"}, client=client
    )
    result = asyncio.run(adapter.fetch_usage())
    asyncio.run(client.aclose())
    assert result.raw_extras["today_tokens"]["uncached_input_tokens"] == 150
    assert result.windows[0].quota_state == "unknown"
    assert "admin-secret" not in result.model_dump_json()


def test_copilot_normalizes_premium_allowance(tmp_path: Path) -> None:
    credentials = tmp_path / "apps.json"
    credentials.write_text(json.dumps({"github.com": {"oauth_token": "secret"}}))
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "copilot_plan": "individual_pro",
                "quota_snapshots": {
                    "premium_interactions": {
                        "entitlement": 300,
                        "remaining": 225,
                        "reset_date": "2026-08-01T00:00:00Z",
                    }
                },
            },
        )
    )
    client = httpx.AsyncClient(transport=transport)
    result = asyncio.run(
        CopilotAdapter("copilot", {"credentials": str(credentials)}, client=client).fetch_usage()
    )
    asyncio.run(client.aclose())
    assert result.windows[0].used_pct == 25
    assert result.raw_extras["remaining"] == 225
    assert "secret" not in result.model_dump_json()


def test_gemini_auth_detection_is_honest_manual_fallback(tmp_path: Path) -> None:
    credentials = tmp_path / "oauth.json"
    expiry = int((datetime.now(UTC) + timedelta(days=5)).timestamp() * 1000)
    credentials.write_text(json.dumps({"access_token": "secret", "expiry_date": expiry}))
    result = asyncio.run(GeminiAdapter("gemini", {"credentials": str(credentials)}).fetch_usage())
    assert result.auth.status == "ok"
    assert result.windows[0].quota_state == "unavailable"
    assert result.raw_extras["manual_fallback"] is True
    assert "secret" not in result.model_dump_json()


def test_xai_management_balance(monkeypatch) -> None:
    monkeypatch.setenv("TEST_XAI_MANAGEMENT", "management-secret")
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={"changes": [{"changeOrigin": "PURCHASE"}], "total": {"val": "-2500"}},
        )
    )
    client = httpx.AsyncClient(transport=transport)
    result = asyncio.run(
        XAIAdapter(
            "xai",
            {"management_key_env": "TEST_XAI_MANAGEMENT", "team_id": "team-fixture"},
            client=client,
        ).fetch_usage()
    )
    asyncio.run(client.aclose())
    assert result.raw_extras["prepaid_balance_cents"] == "-2500"
    assert result.data_source == "official_api"
    assert "management-secret" not in result.model_dump_json()

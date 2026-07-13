import asyncio

import httpx

from quotacompass.adapters.manual import ManualAdapter
from quotacompass.adapters.openrouter import OpenRouterAdapter


def test_manual_adapter_normalizes_configured_windows() -> None:
    adapter = ManualAdapter(
        "manual",
        {
            "label": "Manual provider",
            "windows": [
                {
                    "name": "weekly",
                    "used_pct": 35,
                    "resets_at": "2026-07-17T00:00:00Z",
                },
                {"name": "promo", "quota_state": "unlimited"},
            ],
        },
    )
    result = asyncio.run(adapter.fetch_usage())
    assert result.label == "Manual provider"
    assert result.data_source == "manual"
    assert [window.quota_state for window in result.windows] == ["metered", "unlimited"]


def test_openrouter_uses_official_credit_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("TEST_OPENROUTER_KEY", "private-fixture-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer private-fixture-key"
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200,
                json={"data": {"limit": 100, "usage": 25, "is_free_tier": False}},
            )
        return httpx.Response(
            200,
            json={"data": {"total_credits": 120, "total_usage": 30}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenRouterAdapter("openrouter", {"api_key_env": "TEST_OPENROUTER_KEY"}, client=client)
    result = asyncio.run(adapter.fetch_usage())
    asyncio.run(client.aclose())
    assert result.windows[0].used_pct == 25
    assert result.support_tier == "stable"
    assert result.data_source == "official_api"
    assert "private-fixture-key" not in result.model_dump_json()

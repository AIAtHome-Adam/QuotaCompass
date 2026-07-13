from __future__ import annotations

import asyncio

import httpx
import pytest

from quotacompass.adapters.base import AdapterError
from quotacompass.adapters.claude_oauth import ClaudeOAuthAdapter


def test_provider_request_allows_only_declared_https_hosts() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ClaudeOAuthAdapter("claude", client=client)

    response = asyncio.run(
        adapter.request(client, "GET", "https://api.anthropic.com/allowed")
    )
    assert response.status_code == 200
    assert seen == ["https://api.anthropic.com/allowed"]

    for blocked in (
        "https://telemetry.example/collect",
        "http://api.anthropic.com/insecure",
        "https://api.anthropic.com.evil.example/collect",
    ):
        with pytest.raises(AdapterError, match="unapproved HTTPS host") as raised:
            asyncio.run(adapter.request(client, "GET", blocked))
        assert raised.value.code == "network_policy"

    assert seen == ["https://api.anthropic.com/allowed"]
    asyncio.run(client.aclose())


def test_every_networked_adapter_declares_an_allowlist() -> None:
    from quotacompass.adapters.anthropic_api import AnthropicAPIAdapter
    from quotacompass.adapters.codex_oauth import CodexOAuthAdapter
    from quotacompass.adapters.copilot import CopilotAdapter
    from quotacompass.adapters.cursor import CursorAdapter
    from quotacompass.adapters.nous import NousAdapter
    from quotacompass.adapters.openrouter import OpenRouterAdapter
    from quotacompass.adapters.xai import XAIAdapter

    adapters = (
        AnthropicAPIAdapter,
        ClaudeOAuthAdapter,
        CodexOAuthAdapter,
        CopilotAdapter,
        CursorAdapter,
        NousAdapter,
        OpenRouterAdapter,
        XAIAdapter,
    )
    assert all(adapter.allowed_hosts for adapter in adapters)
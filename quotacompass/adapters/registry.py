from __future__ import annotations

from quotacompass.adapters.anthropic_api import AnthropicAPIAdapter
from quotacompass.adapters.base import Adapter
from quotacompass.adapters.claude_oauth import ClaudeOAuthAdapter
from quotacompass.adapters.codex_oauth import CodexOAuthAdapter
from quotacompass.adapters.copilot import CopilotAdapter
from quotacompass.adapters.cursor import CursorAdapter
from quotacompass.adapters.gemini import GeminiAdapter
from quotacompass.adapters.manual import ManualAdapter
from quotacompass.adapters.nous import NousAdapter
from quotacompass.adapters.opencode import OpenCodeAdapter
from quotacompass.adapters.openrouter import OpenRouterAdapter
from quotacompass.adapters.xai import XAIAdapter
from quotacompass.core.config import AppConfig

ADAPTERS: dict[str, type[Adapter]] = {
    "anthropic_api": AnthropicAPIAdapter,
    "claude_oauth": ClaudeOAuthAdapter,
    "codex_oauth": CodexOAuthAdapter,
    "copilot": CopilotAdapter,
    "cursor": CursorAdapter,
    "gemini": GeminiAdapter,
    "manual": ManualAdapter,
    "nous": NousAdapter,
    "opencode": OpenCodeAdapter,
    "openrouter": OpenRouterAdapter,
    "xai": XAIAdapter,
}


def configured_adapters(config: AppConfig) -> list[Adapter]:
    adapters: list[Adapter] = []
    for provider_id, provider in config.providers.items():
        if not provider.enabled:
            continue
        adapter_type = ADAPTERS.get(provider.adapter)
        if adapter_type is None:
            continue
        options = provider.model_dump(exclude={"adapter", "enabled"})
        options.update(provider.model_extra or {})
        options["label"] = provider.label or provider_id
        options.setdefault("timezone", config.timezone)
        adapters.append(adapter_type(provider_id, options))
    return adapters

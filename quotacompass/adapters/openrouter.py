from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult, retry_after_seconds
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    SupportTier,
)


class OpenRouterAdapter(Adapter):
    default_support_tier = SupportTier.STABLE
    default_data_source = DataSource.OFFICIAL_API
    allowed_hosts = frozenset({"openrouter.ai"})
    key_endpoint = "https://openrouter.ai/api/v1/key"
    credits_endpoint = "https://openrouter.ai/api/v1/credits"

    def __init__(
        self,
        provider_id: str,
        options: dict[str, Any] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, options)
        self.key_env = str(self.options.get("api_key_env", "OPENROUTER_API_KEY"))
        self.client = client
        self._owns_client = client is None

    def _key(self) -> str:
        value = os.getenv(self.key_env)
        if not value:
            raise AdapterError(
                "credentials_missing",
                f"Environment variable {self.key_env} is not set",
            )
        return value

    async def probe(self) -> ProbeResult:
        return ProbeResult(bool(os.getenv(self.key_env)), f"Environment variable {self.key_env}")

    async def fetch_usage(self) -> ProviderStatus:
        key = self._key()
        client = self.client or httpx.AsyncClient(timeout=15)
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        try:
            key_response, credits_response = await __import__("asyncio").gather(
                self.request(client, "GET", self.key_endpoint, headers=headers),
                self.request(client, "GET", self.credits_endpoint, headers=headers),
            )
            if key_response.status_code == 401:
                raise AdapterError("auth_expired", "OpenRouter rejected the configured API key")
            key_response.raise_for_status()
            credits_response.raise_for_status()
            key_payload = key_response.json().get("data", key_response.json())
            credits_payload = credits_response.json().get("data", credits_response.json())
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"OpenRouter returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"OpenRouter request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        limit = key_payload.get("limit")
        usage = key_payload.get("usage")
        used_pct = None
        if isinstance(limit, (int, float)) and limit > 0 and isinstance(usage, (int, float)):
            used_pct = max(0.0, min(100.0, usage / limit * 100))
        now = datetime.now(UTC)
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="api",
            support_tier=self.support_tier,
            data_source=DataSource.OFFICIAL_API,
            auth=AuthStatus(status=AuthState.OK, source=f"env:{self.key_env}"),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:credits",
                    name="credits",
                    quota_state=(
                        QuotaState.METERED if used_pct is not None else QuotaState.UNKNOWN
                    ),
                    used_pct=used_pct,
                )
            ],
            raw_extras={
                "credits_remaining": credits_payload.get("total_credits"),
                "credits_usage": credits_payload.get("total_usage"),
                "is_free_tier": key_payload.get("is_free_tier"),
                "limit": limit,
                "usage": usage,
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

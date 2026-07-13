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


class AnthropicAPIAdapter(Adapter):
    default_support_tier = SupportTier.STABLE
    default_data_source = DataSource.OFFICIAL_API
    allowed_hosts = frozenset({"api.anthropic.com"})
    endpoint = "https://api.anthropic.com/v1/organizations/usage_report/messages"

    def __init__(
        self,
        provider_id: str,
        options: dict[str, Any] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, options)
        self.key_env = str(self.options.get("admin_key_env", "ANTHROPIC_ADMIN_KEY"))
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        return ProbeResult(bool(os.getenv(self.key_env)), f"Environment variable {self.key_env}")

    async def fetch_usage(self) -> ProviderStatus:
        key = os.getenv(self.key_env)
        if not key:
            raise AdapterError(
                "credentials_missing", f"Environment variable {self.key_env} is not set"
            )
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        client = self.client or httpx.AsyncClient(timeout=20)
        try:
            response = await self.request(client, "GET",
                self.endpoint,
                params={"starting_at": start.isoformat(), "bucket_width": "1d", "limit": 1},
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Accept": "application/json",
                },
            )
            if response.status_code in {401, 403}:
                raise AdapterError("auth_expired", "Anthropic rejected the Admin API key")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"Anthropic Admin usage returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"Anthropic Admin request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        totals: dict[str, int] = {}
        for bucket in payload.get("data") or []:
            for result in bucket.get("results") or []:
                for field in (
                    "uncached_input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                ):
                    value = result.get(field)
                    if isinstance(value, int):
                        totals[field] = totals.get(field, 0) + value
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="api",
            support_tier=self.support_tier,
            data_source=self.data_source,
            auth=AuthStatus(status=AuthState.OK, source=f"env:{self.key_env}"),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:usage",
                    name="usage",
                    quota_state=QuotaState.UNKNOWN,
                )
            ],
            raw_extras={"today_tokens": totals, "has_more": payload.get("has_more")},
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

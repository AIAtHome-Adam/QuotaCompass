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


class XAIAdapter(Adapter):
    default_support_tier = SupportTier.BETA
    default_data_source = DataSource.OFFICIAL_API
    allowed_hosts = frozenset({"management-api.x.ai"})
    base_url = "https://management-api.x.ai"

    def __init__(
        self,
        provider_id: str,
        options: dict[str, Any] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, options)
        self.management_key_env = str(self.options.get("management_key_env", "XAI_MANAGEMENT_KEY"))
        self.api_key_env = str(self.options.get("api_key_env", "XAI_API_KEY"))
        self.team_id = self.options.get("team_id") or os.getenv("XAI_TEAM_ID")
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        management = bool(os.getenv(self.management_key_env) and self.team_id)
        inference = bool(os.getenv(self.api_key_env))
        return ProbeResult(
            management or inference,
            f"env:{self.management_key_env} + team_id, or env:{self.api_key_env}",
        )

    async def fetch_usage(self) -> ProviderStatus:
        now = datetime.now(UTC)
        management_key = os.getenv(self.management_key_env)
        if not management_key or not self.team_id:
            if not os.getenv(self.api_key_env):
                raise AdapterError(
                    "credentials_missing", "No xAI API or Management API key is configured"
                )
            return ProviderStatus(
                id=self.provider_id,
                label=self.label,
                kind="api",
                support_tier=SupportTier.EXPERIMENTAL,
                data_source=DataSource.LOCAL_DERIVED,
                auth=AuthStatus(status=AuthState.OK, source=f"env:{self.api_key_env}"),
                windows=[
                    LimitWindow(
                        window_id=f"{self.provider_id}:credits",
                        name="credits",
                        quota_state=QuotaState.UNAVAILABLE,
                    )
                ],
                raw_extras={
                    "manual_fallback": True,
                    "reason": "xAI billing requires a separate Management API key and team_id",
                },
                fetched_at=now,
                last_success_at=now,
                stale_after=now + timedelta(hours=1),
            )

        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await self.request(client, "GET",
                f"{self.base_url}/v1/billing/teams/{self.team_id}/prepaid/balance",
                headers={
                    "Authorization": f"Bearer {management_key}",
                    "Accept": "application/json",
                },
            )
            if response.status_code in {401, 403}:
                raise AdapterError("auth_expired", "xAI rejected the Management API key")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"xAI billing returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"xAI billing request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="api",
            support_tier=self.support_tier,
            data_source=self.data_source,
            auth=AuthStatus(status=AuthState.OK, source=f"env:{self.management_key_env}"),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:prepaid",
                    name="credits",
                    quota_state=QuotaState.UNKNOWN,
                )
            ],
            raw_extras={
                "prepaid_balance_cents": (payload.get("total") or {}).get("val"),
                "balance_change_count": len(payload.get("changes") or []),
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

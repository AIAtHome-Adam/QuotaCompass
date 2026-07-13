from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    ReauthHint,
    SupportTier,
)


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


class ClaudeOAuthAdapter(Adapter):
    default_support_tier = SupportTier.STABLE
    allowed_hosts = frozenset({"api.anthropic.com"})
    reauth_command = "claude login"
    reauth_automatable = True
    endpoint = "https://api.anthropic.com/api/oauth/usage"

    def __init__(
        self,
        provider_id: str,
        options: dict[str, Any] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, options)
        configured = self.options.get("credentials")
        self.credentials = (
            Path(configured).expanduser()
            if configured
            else Path.home() / ".claude" / ".credentials.json"
        )
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        return ProbeResult(self.credentials.is_file(), str(self.credentials))

    def _credentials(self) -> tuple[str, datetime | None, dict[str, Any]]:
        try:
            root = json.loads(self.credentials.read_text(encoding="utf-8"))
            oauth = root["claudeAiOauth"]
            return oauth["accessToken"], _datetime(oauth.get("expiresAt")), oauth
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AdapterError(
                "credentials_unreadable", f"Claude credentials are unavailable: {exc}"
            ) from exc

    async def fetch_usage(self) -> ProviderStatus:
        token, expires_at, metadata = self._credentials()
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await self.request(client, "GET",
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "anthropic-beta": "oauth-2025-04-20",
                    "Accept": "application/json",
                },
            )
            if response.status_code == 401:
                raise AdapterError("auth_expired", "Claude authentication has expired")
            if response.status_code == 429:
                raise AdapterError(
                    "rate_limited",
                    "Claude usage endpoint rate-limited the poll",
                    retryable=True,
                    retry_after=retry_after_seconds(response.headers.get("Retry-After")),
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"Claude usage returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"Claude usage request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        now = datetime.now(UTC)
        windows: list[LimitWindow] = []
        names = {"five_hour": "5h", "seven_day": "weekly", "seven_day_opus": "weekly-opus"}
        for key, name in names.items():
            item = payload.get(key)
            if not isinstance(item, dict):
                continue
            utilization = item.get("utilization")
            windows.append(
                LimitWindow(
                    window_id=f"{self.provider_id}:{key}",
                    name=name,
                    quota_state=QuotaState.METERED
                    if utilization is not None
                    else QuotaState.UNKNOWN,
                    used_pct=utilization,
                    resets_at=_datetime(item.get("resets_at")),
                    estimated=False,
                )
            )
        for index, item in enumerate(payload.get("weekly_scoped") or []):
            if not isinstance(item, dict):
                continue
            scope = item.get("scope") or {}
            model = ((scope.get("model") or {}).get("display_name")) or f"model-{index + 1}"
            windows.append(
                LimitWindow(
                    window_id=f"{self.provider_id}:weekly-scoped:{index}",
                    name=f"weekly-{model}",
                    quota_state=QuotaState.METERED
                    if item.get("utilization") is not None
                    else QuotaState.UNKNOWN,
                    used_pct=item.get("utilization"),
                    resets_at=_datetime(item.get("resets_at")),
                )
            )
        auth_state = AuthState.OK
        if expires_at and expires_at <= now:
            auth_state = AuthState.EXPIRED
        elif expires_at and expires_at <= now + timedelta(days=3):
            auth_state = AuthState.EXPIRING_SOON
        return ProviderStatus(
            id=self.provider_id,
            label=self.options.get("label", "Claude subscription"),
            kind="subscription",
            support_tier=SupportTier.STABLE,
            data_source=DataSource.UNOFFICIAL_API,
            auth=AuthStatus(
                status=auth_state,
                expires_at=expires_at,
                source=str(self.credentials),
                reauth=ReauthHint(command="claude login", automatable=True),
            ),
            windows=windows,
            raw_extras={"subscription_type": metadata.get("subscriptionType")},
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

from __future__ import annotations

import json
import os
import subprocess
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


def _find_token(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("oauth_token", "token", "access_token"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        for candidate in value.values():
            found = _find_token(candidate)
            if found:
                return found
    if isinstance(value, list):
        for candidate in value:
            found = _find_token(candidate)
            if found:
                return found
    return None


class CopilotAdapter(Adapter):
    default_support_tier = SupportTier.BETA
    default_data_source = DataSource.UNOFFICIAL_API
    allowed_hosts = frozenset({"api.github.com"})
    endpoint = "https://api.github.com/copilot_internal/user"
    reauth_command = "gh auth login"
    reauth_automatable = True

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
            else Path.home() / ".config" / "github-copilot" / "apps.json"
        )
        self.token_env = str(self.options.get("token_env", "GITHUB_TOKEN"))
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        return ProbeResult(
            bool(os.getenv(self.token_env)) or self.credentials.is_file(),
            f"{self.credentials}, env:{self.token_env}, or gh CLI",
        )

    def _token(self) -> tuple[str, str]:
        if os.getenv(self.token_env):
            return os.environ[self.token_env], f"env:{self.token_env}"
        if self.credentials.is_file():
            try:
                token = _find_token(json.loads(self.credentials.read_text(encoding="utf-8")))
                if token:
                    return token, str(self.credentials)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
            )
            if result.stdout.strip():
                return result.stdout.strip(), "gh auth token"
        except (OSError, subprocess.SubprocessError):
            pass
        raise AdapterError("credentials_missing", "No GitHub Copilot credential was found")

    async def fetch_usage(self) -> ProviderStatus:
        token, source = self._token()
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await self.request(client, "GET",
                self.endpoint,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/json",
                    "User-Agent": "QuotaCompass/0.1",
                },
            )
            if response.status_code in {401, 403}:
                raise AdapterError("auth_expired", "GitHub rejected the Copilot credential")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"GitHub Copilot usage returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"GitHub Copilot request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        quota = (payload.get("quota_snapshots") or {}).get("premium_interactions") or {}
        entitlement = quota.get("entitlement")
        remaining = quota.get("remaining")
        used_pct = quota.get("percent_remaining")
        if isinstance(used_pct, (int, float)):
            used_pct = 100 - used_pct
        elif (
            isinstance(entitlement, (int, float))
            and entitlement > 0
            and isinstance(remaining, (int, float))
        ):
            used_pct = (entitlement - remaining) / entitlement * 100
        reset = quota.get("reset_date") or payload.get("quota_reset_date")
        resets_at = None
        if reset:
            try:
                resets_at = datetime.fromisoformat(str(reset).replace("Z", "+00:00"))
            except ValueError:
                resets_at = None
        now = datetime.now(UTC)
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="subscription",
            support_tier=self.support_tier,
            data_source=self.data_source,
            auth=AuthStatus(
                status=AuthState.OK,
                source=source,
                reauth=ReauthHint(command=self.reauth_command, automatable=True),
            ),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:premium-requests",
                    name="monthly",
                    quota_state=(
                        QuotaState.METERED if used_pct is not None else QuotaState.UNKNOWN
                    ),
                    used_pct=used_pct,
                    resets_at=resets_at,
                )
            ],
            raw_extras={
                "plan": payload.get("copilot_plan"),
                "entitlement": entitlement,
                "remaining": remaining,
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

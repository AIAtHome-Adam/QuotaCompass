from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult
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


class GeminiAdapter(Adapter):
    """Auth-health adapter; active Gemini quota remains manual until a stable API exists."""

    default_support_tier = SupportTier.EXPERIMENTAL
    default_data_source = DataSource.LOCAL_DERIVED
    reauth_command = "gemini auth login"
    reauth_automatable = True

    def __init__(self, provider_id: str, options: dict[str, Any] | None = None) -> None:
        super().__init__(provider_id, options)
        configured = self.options.get("credentials")
        self.credentials = (
            Path(configured).expanduser()
            if configured
            else Path.home() / ".gemini" / "oauth_creds.json"
        )
        self.key_env = str(self.options.get("api_key_env", "GEMINI_API_KEY"))

    async def probe(self) -> ProbeResult:
        available = self.credentials.is_file() or bool(os.getenv(self.key_env))
        return ProbeResult(available, f"{self.credentials} or env:{self.key_env}")

    async def fetch_usage(self) -> ProviderStatus:
        now = datetime.now(UTC)
        expires_at = None
        source = None
        if self.credentials.is_file():
            try:
                payload = json.loads(self.credentials.read_text(encoding="utf-8"))
                expiry = payload.get("expiry") or payload.get("expiry_date")
                if isinstance(expiry, (int, float)):
                    expires_at = datetime.fromtimestamp(
                        expiry / 1000 if expiry > 10_000_000_000 else expiry, UTC
                    )
                elif expiry:
                    expires_at = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                source = str(self.credentials)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise AdapterError(
                    "credentials_unreadable", f"Gemini credentials are unavailable: {exc}"
                ) from exc
        elif os.getenv(self.key_env):
            source = f"env:{self.key_env}"
        else:
            raise AdapterError(
                "credentials_missing", "No Gemini OAuth credentials or API key were found"
            )
        auth_state = AuthState.OK
        if expires_at and expires_at <= now:
            auth_state = AuthState.EXPIRED
        elif expires_at and expires_at <= now + timedelta(days=3):
            auth_state = AuthState.EXPIRING_SOON
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="subscription",
            support_tier=self.support_tier,
            data_source=self.data_source,
            auth=AuthStatus(
                status=auth_state,
                expires_at=expires_at,
                source=source,
                reauth=ReauthHint(command=self.reauth_command, automatable=True),
            ),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:quota",
                    name="quota",
                    quota_state=QuotaState.UNAVAILABLE,
                )
            ],
            raw_extras={
                "manual_fallback": True,
                "reason": "Active Gemini limits are shown in AI Studio and vary by project/model",
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(hours=1),
        )

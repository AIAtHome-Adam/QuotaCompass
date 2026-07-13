from __future__ import annotations

import base64
import json
import os
import sqlite3
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


class CursorAdapter(Adapter):
    default_support_tier = SupportTier.BETA
    default_data_source = DataSource.UNOFFICIAL_API
    allowed_hosts = frozenset({"cursor.com"})
    endpoint = "https://cursor.com/api/usage-summary"
    reauth_command = "Open Cursor and sign in"

    def __init__(
        self,
        provider_id: str,
        options: dict[str, Any] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, options)
        configured = self.options.get("state_db")
        if configured:
            self.credentials = Path(configured).expanduser()
        elif os.name == "nt" and os.getenv("APPDATA"):
            self.credentials = (
                Path(os.environ["APPDATA"]) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
            )
        else:
            self.credentials = (
                Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
            )
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        return ProbeResult(self.credentials.is_file(), str(self.credentials))

    def _token(self) -> tuple[str, str, datetime | None]:
        try:
            connection = sqlite3.connect(f"file:{self.credentials.as_posix()}?mode=ro", uri=True)
            try:
                row = connection.execute(
                    "SELECT value FROM ItemTable WHERE key='cursorAuth/accessToken'"
                ).fetchone()
            finally:
                connection.close()
            if not row:
                raise KeyError("cursorAuth/accessToken")
            token = row[0]
            part = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            expires_at = datetime.fromtimestamp(claims["exp"], UTC) if claims.get("exp") else None
            return token, claims["sub"], expires_at
        except (OSError, sqlite3.Error, KeyError, IndexError, ValueError) as exc:
            raise AdapterError(
                "credentials_unreadable", f"Cursor credentials are unavailable: {exc}"
            ) from exc

    async def fetch_usage(self) -> ProviderStatus:
        token, user_id, expires_at = self._token()
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await self.request(client, "GET",
                self.endpoint,
                headers={
                    "Cookie": f"WorkosCursorSessionToken={user_id}%3A%3A{token}",
                    "Referer": "https://www.cursor.com/settings",
                    "Accept": "application/json",
                },
            )
            if response.status_code in {401, 403}:
                raise AdapterError("auth_expired", "Cursor authentication has expired")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"Cursor usage returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"Cursor usage request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        now = datetime.now(UTC)
        plan = (payload.get("individualUsage") or {}).get("plan") or {}
        unlimited = bool(payload.get("isUnlimited"))
        used_pct = plan.get("totalPercentUsed")
        if used_pct is None and plan.get("limit"):
            used_pct = plan.get("used", 0) / plan["limit"] * 100
        resets_at = None
        if payload.get("billingCycleEnd"):
            resets_at = datetime.fromisoformat(
                str(payload["billingCycleEnd"]).replace("Z", "+00:00")
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
                source=str(self.credentials),
                reauth=ReauthHint(command=self.reauth_command),
            ),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:billing-cycle",
                    name="monthly",
                    quota_state=(
                        QuotaState.UNLIMITED
                        if unlimited
                        else QuotaState.METERED
                        if used_pct is not None
                        else QuotaState.UNKNOWN
                    ),
                    used_pct=None if unlimited else used_pct,
                    resets_at=resets_at,
                )
            ],
            raw_extras={
                "membership_type": payload.get("membershipType"),
                "plan_used": plan.get("used"),
                "plan_limit": plan.get("limit"),
                "plan_remaining": plan.get("remaining"),
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

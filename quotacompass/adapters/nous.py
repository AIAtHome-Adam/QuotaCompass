from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult, retry_after_seconds
from quotacompass.core.discovery import credential_candidates
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


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _default_credentials() -> Path:
    native = Path.home() / ".hermes" / "auth.json"
    if native.exists():
        return native
    for candidate in credential_candidates():
        if candidate.adapter == "hermes" and candidate.exists:
            path = candidate.path / "auth.json" if candidate.path.is_dir() else candidate.path
            if path.exists():
                return path
    return native


class NousAdapter(Adapter):
    default_support_tier = SupportTier.EXPERIMENTAL
    default_data_source = DataSource.UNOFFICIAL_API
    allowed_hosts = frozenset({"portal.nousresearch.com"})
    reauth_command = "hermes model"
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
        self.credentials = Path(configured).expanduser() if configured else _default_credentials()
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        return ProbeResult(self.credentials.is_file(), str(self.credentials))

    def _auth(self) -> tuple[str, str, datetime | None]:
        try:
            root = json.loads(self.credentials.read_text(encoding="utf-8"))
            state = (root.get("providers") or {}).get("nous") or root.get("nous") or {}
            token = state["access_token"]
            portal = str(state.get("portal_base_url") or "https://portal.nousresearch.com").rstrip(
                "/"
            )
            return token, portal, _parse_datetime(state.get("expires_at"))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AdapterError(
                "credentials_unreadable", f"Nous Portal credentials are unavailable: {exc}"
            ) from exc

    async def fetch_usage(self) -> ProviderStatus:
        token, portal, expires_at = self._auth()
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await self.request(client, "GET",
                f"{portal}/api/oauth/account",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            if response.status_code in {401, 403}:
                raise AdapterError("auth_expired", "Nous Portal authentication has expired")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"Nous Portal account endpoint returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429 or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(exc.response.headers.get("Retry-After")),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"Nous Portal request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        subscription = payload.get("subscription") or {}
        access = payload.get("paid_service_access") or {}
        cap = subscription.get("monthly_credits")
        remaining = subscription.get("credits_remaining")
        used_pct = None
        if (
            isinstance(cap, (int, float))
            and cap > 0
            and isinstance(remaining, (int, float))
            and remaining <= cap
        ):
            used_pct = max(0.0, min(100.0, (cap - remaining) / cap * 100))
        reset = _parse_datetime(subscription.get("current_period_end"))
        now = datetime.now(UTC)
        auth_state = AuthState.OK
        if expires_at and expires_at <= now:
            auth_state = AuthState.EXPIRED
        elif expires_at and expires_at <= now + timedelta(days=3):
            auth_state = AuthState.EXPIRING_SOON
        allowed = access.get("allowed", access.get("paid_access"))
        quota_state = QuotaState.METERED if used_pct is not None else QuotaState.UNKNOWN
        if allowed is False and access.get("total_usable_credits") == 0:
            quota_state = QuotaState.UNAVAILABLE
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
                reauth=ReauthHint(command=self.reauth_command, automatable=True),
            ),
            windows=[
                LimitWindow(
                    window_id=f"{self.provider_id}:subscription",
                    name="monthly",
                    quota_state=quota_state,
                    used_pct=used_pct,
                    resets_at=reset,
                )
            ],
            raw_extras={
                "plan": subscription.get("plan"),
                "monthly_credits": cap,
                "subscription_credits_remaining": remaining,
                "rollover_credits": subscription.get("rollover_credits"),
                "purchased_credits_remaining": access.get("purchased_credits_remaining"),
                "total_usable_credits": access.get("total_usable_credits"),
                "paid_service_access": allowed,
                "access_reason": access.get("reason"),
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=15),
        )

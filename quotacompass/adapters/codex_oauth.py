from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from quotacompass.adapters.base import (
    Adapter,
    AdapterError,
    ProbeResult,
    retry_after_seconds,
)
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    CapacityNotice,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    ReauthHint,
    SupportTier,
)


def _jwt_exp(token: str) -> datetime | None:
    try:
        part = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return datetime.fromtimestamp(payload["exp"], UTC)
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


class CodexOAuthAdapter(Adapter):
    default_support_tier = SupportTier.STABLE
    allowed_hosts = frozenset({"chatgpt.com"})
    reauth_command = "codex login"
    reauth_automatable = True
    endpoint = "https://chatgpt.com/backend-api/wham/usage"

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
            else Path.home() / ".codex" / "auth.json"
        )
        self.client = client
        self._owns_client = client is None

    async def probe(self) -> ProbeResult:
        return ProbeResult(self.credentials.is_file(), str(self.credentials))

    def _credentials(self) -> tuple[str, str, datetime | None]:
        try:
            root = json.loads(self.credentials.read_text(encoding="utf-8"))
            tokens = root["tokens"]
            access = tokens["access_token"]
            return access, tokens["account_id"], _jwt_exp(access)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AdapterError(
                "credentials_unreadable", f"Codex credentials are unavailable: {exc}"
            ) from exc

    @staticmethod
    def _windows(
        payload: dict[str, Any], provider_id: str
    ) -> tuple[list[LimitWindow], list[CapacityNotice]]:
        candidates: list[dict[str, Any]] = []
        rate_limit = payload.get("rate_limit") or payload
        for key in ("primary_window", "secondary_window"):
            if isinstance(rate_limit.get(key), dict):
                candidates.append(rate_limit[key])
        windows = []
        for index, item in enumerate(candidates):
            duration = item.get("limit_window_seconds") or item.get("window_seconds")
            name = {18000: "5h", 604800: "weekly"}.get(
                duration, f"custom-{duration or index}"
            )
            reset_at = item.get("reset_at") or item.get("resets_at")
            if isinstance(reset_at, (int, float)):
                reset_at = datetime.fromtimestamp(reset_at, UTC)
            elif reset_at:
                reset_at = datetime.fromisoformat(str(reset_at).replace("Z", "+00:00"))
            used = item.get("used_percent", item.get("used_pct"))
            windows.append(
                LimitWindow(
                    window_id=f"{provider_id}:{duration or index}",
                    name=name,
                    quota_state=QuotaState.METERED
                    if used is not None
                    else QuotaState.UNKNOWN,
                    used_pct=used,
                    resets_at=reset_at,
                    window_duration_seconds=duration,
                )
            )
        notices: list[CapacityNotice] = []
        explicit_rate_limit = payload.get("rate_limit")
        weekly_only = (
            isinstance(explicit_rate_limit, dict)
            and "primary_window" in explicit_rate_limit
            and "secondary_window" in explicit_rate_limit
            and explicit_rate_limit.get("secondary_window") is None
            and isinstance(explicit_rate_limit.get("primary_window"), dict)
            and explicit_rate_limit["primary_window"].get("limit_window_seconds")
            == 604800
            and any(
                window.name == "weekly"
                and window.quota_state == QuotaState.METERED
                and window.used_pct is not None
                for window in windows
            )
            and not any(window.window_duration_seconds == 18000 for window in windows)
        )
        if weekly_only:
            note = (
                "5-hour limit is temporarily unmetered; the weekly limit still applies."
            )
            windows.insert(
                0,
                LimitWindow(
                    window_id=f"{provider_id}:18000-promotion",
                    name="5h",
                    quota_state=QuotaState.UNLIMITED,
                    window_duration_seconds=18000,
                    temporary=True,
                    inferred=True,
                    status_note=note,
                ),
            )
            notices.append(
                CapacityNotice(
                    notice_id=f"{provider_id}:short-window-unmetered",
                    kind="promotion",
                    title="Temporary capacity boost detected",
                    message=note,
                    evidence="valid_weekly_window_with_explicitly_null_secondary_window",
                )
            )
        return windows, notices

    async def fetch_usage(self) -> ProviderStatus:
        token, account_id, expires_at = self._credentials()
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await self.request(client, "GET",
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "ChatGPT-Account-Id": account_id,
                },
            )
            if response.status_code == 401:
                raise AdapterError("auth_expired", "Codex authentication has expired")
            if response.status_code == 429:
                raise AdapterError(
                    "rate_limited",
                    "Codex usage endpoint rate-limited the poll",
                    retryable=True,
                    retry_after=retry_after_seconds(
                        response.headers.get("Retry-After")
                    ),
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "http_error",
                f"Codex usage returned HTTP {exc.response.status_code}",
                retryable=exc.response.status_code == 429
                or exc.response.status_code >= 500,
                retry_after=retry_after_seconds(
                    exc.response.headers.get("Retry-After")
                ),
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(
                "network_error", f"Codex usage request failed: {exc}", retryable=True
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()
        now = datetime.now(UTC)
        auth_state = AuthState.OK
        if expires_at and expires_at <= now:
            auth_state = AuthState.EXPIRED
        elif expires_at and expires_at <= now + timedelta(days=3):
            auth_state = AuthState.EXPIRING_SOON
        windows, notices = self._windows(payload, self.provider_id)
        return ProviderStatus(
            id=self.provider_id,
            label=self.options.get("label", "ChatGPT / Codex"),
            kind="subscription",
            support_tier=SupportTier.STABLE,
            data_source=DataSource.UNOFFICIAL_API,
            account_hint=f"…{account_id[-6:]}",
            auth=AuthStatus(
                status=auth_state,
                expires_at=expires_at,
                source=str(self.credentials),
                reauth=ReauthHint(command="codex login", automatable=True),
            ),
            windows=windows,
            capacity_notices=notices,
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    ProviderStatus,
    ReauthHint,
    SupportTier,
)


@dataclass(frozen=True)
class ProbeResult:
    available: bool
    detail: str


class Adapter(ABC):
    default_support_tier = SupportTier.EXPERIMENTAL
    default_data_source = DataSource.UNOFFICIAL_API
    reauth_command: str | None = None
    reauth_automatable: bool = False
    allowed_hosts: frozenset[str] = frozenset()

    def __init__(self, provider_id: str, options: dict[str, Any] | None = None) -> None:
        self.provider_id = provider_id
        self.options = options or {}

    @property
    def label(self) -> str:
        return str(self.options.get("label") or self.provider_id)

    @property
    def support_tier(self) -> SupportTier:
        value = self.options.get("support_tier") or self.default_support_tier
        return SupportTier(value)

    @property
    def data_source(self) -> DataSource:
        value = self.options.get("data_source") or self.default_data_source
        return DataSource(value)

    def error_auth(self, error_code: str) -> AuthStatus:
        status = AuthState.EXPIRED if error_code == "auth_expired" else AuthState.UNKNOWN
        credentials = getattr(self, "credentials", None)
        reauth = (
            ReauthHint(command=self.reauth_command, automatable=self.reauth_automatable)
            if self.reauth_command
            else None
        )
        return AuthStatus(
            status=status,
            source=str(credentials) if credentials else None,
            reauth=reauth,
        )

    async def request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a provider request only to this adapter's explicit HTTPS hosts."""
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or hostname not in self.allowed_hosts:
            raise AdapterError(
                "network_policy",
                f"Blocked outbound request for {self.provider_id}: unapproved HTTPS host",
            )
        return await client.request(method, url, **kwargs)

    @abstractmethod
    async def probe(self) -> ProbeResult:
        """Check whether the adapter can run without exposing credentials."""

    @abstractmethod
    async def fetch_usage(self) -> ProviderStatus:
        """Return a normalized provider snapshot or raise an adapter-specific error."""

    async def close(self) -> None:
        """Release optional adapter resources."""
        return None


def retry_after_seconds(value: str | None, *, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=UTC)
            return max(0.0, (target - (now or datetime.now(UTC))).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class AdapterError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after

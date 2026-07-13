from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthState(StrEnum):
    OK = "ok"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    ERROR = "error"
    UNKNOWN = "unknown"


class FetchState(StrEnum):
    OK = "ok"
    STALE = "stale"
    ERROR = "error"


class QuotaState(StrEnum):
    METERED = "metered"
    UNLIMITED = "unlimited"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class SupportTier(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    EXPERIMENTAL = "experimental"


class DataSource(StrEnum):
    OFFICIAL_API = "official_api"
    UNOFFICIAL_API = "unofficial_api"
    LOCAL_DERIVED = "local_derived"
    MANUAL = "manual"


class ReauthHint(BaseModel):
    command: str | None = None
    helper_script: str | None = None
    automatable: bool = False


class AuthStatus(BaseModel):
    status: AuthState = AuthState.UNKNOWN
    expires_at: datetime | None = None
    source: str | None = None
    reauth: ReauthHint | None = None


class LimitWindow(BaseModel):
    model_config = ConfigDict(extra="allow")

    window_id: str
    name: str
    quota_state: QuotaState = QuotaState.UNKNOWN
    used_pct: float | None = Field(default=None, ge=0, le=100)
    resets_at: datetime | None = None
    resets_in_seconds: int | None = Field(default=None, ge=0)
    window_duration_seconds: int | None = Field(default=None, gt=0)
    estimated: bool = False
    temporary: bool = False
    inferred: bool = False
    status_note: str | None = None

    @field_validator("used_pct")
    @classmethod
    def metered_requires_percentage(cls, value: float | None) -> float | None:
        return value

    def seconds_until_reset(self, now: datetime | None = None) -> int | None:
        if self.resets_at is None:
            return None
        current = now or utc_now()
        return max(0, int((self.resets_at - current).total_seconds()))


class FetchError(BaseModel):
    code: str
    category: str
    retryable: bool = False
    message: str
    user_action: str | None = None


class CapacityNotice(BaseModel):
    notice_id: str
    kind: str = "capacity_change"
    title: str
    message: str
    temporary: bool = True
    inferred: bool = True
    confidence: str = "high"
    evidence: str | None = None


class ProviderStatus(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    label: str
    kind: str
    support_tier: SupportTier = SupportTier.EXPERIMENTAL
    data_source: DataSource
    account_hint: str | None = None
    auth: AuthStatus = Field(default_factory=AuthStatus)
    windows: list[LimitWindow] = Field(default_factory=list)
    capacity_notices: list[CapacityNotice] = Field(default_factory=list)
    raw_extras: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime
    last_success_at: datetime | None = None
    fetch_status: FetchState = FetchState.OK
    fetch_error: FetchError | None = None
    stale_after: datetime


class ScoreBreakdown(BaseModel):
    headroom: float = 0
    urgency: float = 0
    recovery: float = 0
    promotion: float = 0
    capability: float = 1
    health_penalty: float = 0
    priority: float = 0


class AdvisorRank(BaseModel):
    id: str
    score: float
    reason: str
    breakdown: ScoreBreakdown
    excluded: bool = False


class ExpiringUnused(BaseModel):
    id: str
    window: str
    unused_pct: float
    resets_at: datetime
    note: str


class AdvisorStatus(BaseModel):
    suggestion: str | None = None
    ranking: list[AdvisorRank] = Field(default_factory=list)
    expiring_unused: list[ExpiringUnused] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    schema_version: int = 1
    generated_at: datetime = Field(default_factory=utc_now)
    generator: str = "quotacompass 0.1.0"
    providers: list[ProviderStatus] = Field(default_factory=list)
    advisor: AdvisorStatus = Field(default_factory=AdvisorStatus)

    @model_validator(mode="after")
    def stamp_reset_countdowns(self) -> StateSnapshot:
        """Keep serialized relative values anchored to this snapshot's generation time."""
        for provider in self.providers:
            for window in provider.windows:
                window.resets_in_seconds = window.seconds_until_reset(self.generated_at)
        return self

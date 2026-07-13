from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotacompass.core.config import AdvisorConfig
from quotacompass.core.models import (
    AdvisorRank,
    AdvisorStatus,
    AuthState,
    ExpiringUnused,
    FetchState,
    ProviderStatus,
    QuotaState,
    ScoreBreakdown,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _health_key(provider: ProviderStatus) -> tuple[int, int, float]:
    auth = (
        2
        if provider.auth.status == AuthState.OK
        else (
            1
            if provider.auth.status in {AuthState.EXPIRING_SOON, AuthState.UNKNOWN}
            else 0
        )
    )
    fetch = (
        2
        if provider.fetch_status == FetchState.OK
        else (1 if provider.fetch_status == FetchState.STALE else 0)
    )
    success = provider.last_success_at.timestamp() if provider.last_success_at else 0.0
    return auth, fetch, success


def advise(
    providers: list[ProviderStatus],
    config: AdvisorConfig | None = None,
    *,
    now: datetime | None = None,
    task: str | None = None,
) -> AdvisorStatus:
    settings = config or AdvisorConfig()
    current = now or _now()
    ranking: list[AdvisorRank] = []
    nudges: list[ExpiringUnused] = []
    linked_groups: dict[str, list[ProviderStatus]] = {}
    for provider in providers:
        linked = provider.raw_extras.get("linked_account")
        if linked:
            linked_groups.setdefault(str(linked), []).append(provider)
    representatives = {
        linked: max(group, key=_health_key).id
        for linked, group in linked_groups.items()
    }
    task_weights = settings.task_weights.get(task, {}) if task else {}

    for provider in providers:
        linked = provider.raw_extras.get("linked_account")
        linked_duplicate = bool(linked and representatives[str(linked)] != provider.id)
        metered = [
            window
            for window in provider.windows
            if window.quota_state == QuotaState.METERED and window.used_pct is not None
        ]
        excluded = linked_duplicate or (
            not metered
            and not any(
                window.quota_state == QuotaState.UNLIMITED
                for window in provider.windows
            )
        )
        headroom = min((1 - window.used_pct / 100 for window in metered), default=1.0)
        promotion_active = any(
            notice.kind == "promotion" and notice.temporary
            for notice in provider.capacity_notices
        )
        urgency = 0.0
        recovery = 0.0
        for window in metered:
            if window.resets_at is None:
                continue
            until = window.resets_at - current
            unused = 100 - window.used_pct
            within = timedelta(hours=settings.nudge_threshold.within_hours)
            if (
                timedelta(0) <= until <= within
                and unused >= settings.nudge_threshold.unused_pct
            ):
                closeness = 1 - (until.total_seconds() / within.total_seconds())
                urgency = max(urgency, (unused / 100) * (0.5 + 0.5 * closeness))
                if not linked_duplicate:
                    nudges.append(
                        ExpiringUnused(
                            id=provider.id,
                            window=window.name,
                            unused_pct=round(unused, 1),
                            resets_at=window.resets_at,
                            note=f"{unused:.0f}% of {provider.label} {window.name} quota resets soon",
                        )
                    )
            duration = window.window_duration_seconds
            if (
                duration
                and duration <= 6 * 3600
                and timedelta(0) <= until <= timedelta(seconds=duration)
            ):
                closeness = 1 - until.total_seconds() / duration
                recovery = max(recovery, (window.used_pct / 100) * closeness)

        health_penalty = 0.0
        if provider.fetch_status == FetchState.STALE:
            health_penalty += 0.2
        elif provider.fetch_status == FetchState.ERROR:
            health_penalty += 0.6
        if provider.auth.status in {AuthState.EXPIRED, AuthState.ERROR}:
            health_penalty += 0.8
        priority = float(provider.raw_extras.get("priority", 1.0)) * 0.05
        capability = max(0.0, float(task_weights.get(provider.id, 1.0)))
        breakdown = ScoreBreakdown(
            headroom=round(headroom * 0.45, 4),
            urgency=round(urgency * 0.3, 4),
            recovery=round(recovery * 0.15, 4),
            promotion=round((0.25 * headroom) if promotion_active else 0, 4),
            capability=round(capability, 4),
            health_penalty=round(health_penalty, 4),
            priority=round(priority, 4),
        )
        utility = (
            breakdown.headroom
            + breakdown.urgency
            + breakdown.recovery
            + breakdown.promotion
        )
        score = utility * capability - breakdown.health_penalty + breakdown.priority
        task_note = (
            f"; {task} capability weight {capability:g}"
            if task and capability != 1
            else ""
        )
        if linked_duplicate:
            reason = f"Excluded: shares linked account {linked!s} with {representatives[str(linked)]}"
        elif excluded:
            reason = "Excluded: no comparable metered or unlimited quota is available"
        elif provider.auth.status in {AuthState.EXPIRED, AuthState.ERROR}:
            reason = (
                "Authentication needs attention before this provider can be recommended"
            )
        elif promotion_active:
            reason = (
                "Temporary unmetered 5h lane detected; "
                f"{headroom:.0%} remains in the weekly limit{task_note}"
            )
        elif urgency > 0:
            reason = (
                f"Unused quota is close to resetting; {headroom:.0%} remains in the tightest window"
                f"{task_note}"
            )
        elif recovery > 0:
            reason = (
                f"A short limit window recovers soon; {headroom:.0%} remains{task_note}"
            )
        else:
            reason = (
                f"{headroom:.0%} remains in the tightest reported window{task_note}"
            )
        ranking.append(
            AdvisorRank(
                id=provider.id,
                score=round(score, 4),
                reason=reason,
                breakdown=breakdown,
                excluded=excluded,
            )
        )

    ranking.sort(key=lambda item: (item.excluded, -item.score, item.id))
    suggestion = next(
        (item.id for item in ranking if not item.excluded and item.score > -0.5), None
    )
    nudges.sort(key=lambda item: item.resets_at)
    return AdvisorStatus(suggestion=suggestion, ranking=ranking, expiring_unused=nudges)

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from quotacompass.adapters.base import Adapter, AdapterError
from quotacompass.core.models import AuthStatus, FetchError, FetchState, ProviderStatus


async def poll_adapters(
    adapters: Iterable[Adapter],
    *,
    concurrency: int = 4,
    timeout_seconds: float = 20,
    max_attempts: int = 2,
    base_backoff_seconds: float = 0.5,
) -> list[ProviderStatus]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(adapter: Adapter) -> ProviderStatus:
        async with semaphore:
            now = datetime.now(UTC)
            auth = AuthStatus()
            error: FetchError | None = None
            for attempt in range(max(1, max_attempts)):
                try:
                    return await asyncio.wait_for(adapter.fetch_usage(), timeout=timeout_seconds)
                except TimeoutError:
                    error = FetchError(
                        code="timeout",
                        category="network",
                        retryable=True,
                        message=f"Provider poll exceeded {timeout_seconds:g}s",
                        user_action="Retry later or run quotacompass doctor",
                    )
                    retryable = True
                    retry_after = None
                except AdapterError as exc:
                    auth = adapter.error_auth(exc.code)
                    error = FetchError(
                        code=exc.code,
                        category="adapter",
                        retryable=exc.retryable,
                        message=str(exc),
                        user_action=(
                            f"Run {adapter.reauth_command}"
                            if exc.code == "auth_expired" and adapter.reauth_command
                            else None
                        ),
                    )
                    retryable = exc.retryable
                    retry_after = exc.retry_after
                except Exception as exc:  # adapter isolation boundary
                    error = FetchError(
                        code="unexpected_adapter_error",
                        category="adapter",
                        retryable=False,
                        message=f"{type(exc).__name__}: {exc}",
                        user_action="Run quotacompass doctor and inspect the provider verification log",
                    )
                    retryable = False
                    retry_after = None
                if not retryable or attempt + 1 >= max(1, max_attempts):
                    break
                delay = (
                    min(retry_after, 60.0)
                    if retry_after is not None
                    else min(base_backoff_seconds * (2**attempt), 60.0)
                )
                await asyncio.sleep(delay)
            assert error is not None
            return ProviderStatus(
                id=adapter.provider_id,
                label=adapter.label,
                kind="subscription",
                support_tier=adapter.support_tier,
                data_source=adapter.data_source,
                auth=auth,
                fetched_at=now,
                fetch_status=FetchState.ERROR,
                fetch_error=error,
                stale_after=now + timedelta(minutes=15),
            )

    return list(await asyncio.gather(*(one(adapter) for adapter in adapters)))

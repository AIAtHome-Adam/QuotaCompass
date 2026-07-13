from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable


class PollingScheduler:
    """Single-owner polling loop with jitter and responsive shutdown."""

    def __init__(
        self,
        poll: Callable[[], Awaitable[object]],
        *,
        interval_seconds: float,
        jitter_ratio: float = 0.1,
    ) -> None:
        self.poll = poll
        self.interval_seconds = interval_seconds
        self.jitter_ratio = jitter_ratio
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.last_error: Exception | None = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self.run(), name="quotacompass-poller")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.poll()
                self.last_error = None
            except Exception as exc:  # process boundary: keep serving last-known-good state
                self.last_error = exc
            spread = self.interval_seconds * self.jitter_ratio
            delay = max(1.0, self.interval_seconds + random.uniform(-spread, spread))
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=delay)
            except TimeoutError:
                continue

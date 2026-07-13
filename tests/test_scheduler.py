import asyncio

from quotacompass.core.scheduler import PollingScheduler


def test_scheduler_polls_immediately_and_stops() -> None:
    calls = 0

    async def poll() -> None:
        nonlocal calls
        calls += 1

    async def exercise() -> None:
        scheduler = PollingScheduler(poll, interval_seconds=3600, jitter_ratio=0)
        scheduler.start()
        await asyncio.sleep(0)
        await scheduler.stop()
        assert scheduler.last_error is None

    asyncio.run(exercise())
    assert calls == 1


def test_scheduler_retains_process_after_poll_error() -> None:
    async def failing_poll() -> None:
        raise RuntimeError("fixture failure")

    async def exercise() -> None:
        scheduler = PollingScheduler(failing_poll, interval_seconds=3600, jitter_ratio=0)
        scheduler.start()
        await asyncio.sleep(0)
        await scheduler.stop()
        assert isinstance(scheduler.last_error, RuntimeError)

    asyncio.run(exercise())

from datetime import UTC, datetime

from quotacompass.core.cadence import next_reset


def test_weekly_reset_preserves_wall_clock_across_dst() -> None:
    before_spring_forward = datetime(2026, 3, 7, 17, tzinfo=UTC)

    reset = next_reset(
        "weekly:thu 23:59",
        "America/New_York",
        now=before_spring_forward,
    )

    assert reset.isoformat() == "2026-03-13T03:59:00+00:00"


def test_daily_reset_rolls_to_tomorrow_after_time_passes() -> None:
    now = datetime(2026, 7, 11, 15, tzinfo=UTC)

    reset = next_reset("daily: 08:00", "America/Denver", now=now)

    assert reset.isoformat() == "2026-07-12T14:00:00+00:00"

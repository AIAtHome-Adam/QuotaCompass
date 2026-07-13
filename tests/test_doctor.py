import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotacompass.core.config import AppConfig
from quotacompass.core.doctor import doctor_exit_code, run_doctor
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    ProviderStatus,
    StateSnapshot,
)
from quotacompass.core.statefile import write_snapshot


def test_doctor_diagnoses_stopped_service_and_missing_state(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"server": {"port": 54789}})

    checks = asyncio.run(run_doctor(config, tmp_path, []))
    by_id = {check.id: check for check in checks}

    assert not by_id["service.liveness"].ok
    assert "Start" in by_id["service.liveness"].hint
    assert not by_id["state.freshness"].ok
    assert doctor_exit_code(checks, tmp_path) == 3


def test_doctor_uses_auth_expired_exit_code(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    provider = ProviderStatus(
        id="claude",
        label="Claude",
        kind="subscription",
        data_source=DataSource.UNOFFICIAL_API,
        auth=AuthStatus(status=AuthState.EXPIRED),
        fetched_at=now,
        stale_after=now + timedelta(minutes=10),
    )
    write_snapshot(tmp_path, StateSnapshot(providers=[provider]))

    checks = asyncio.run(run_doctor(AppConfig(), tmp_path, []))

    assert doctor_exit_code(checks, tmp_path) == 4

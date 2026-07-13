import asyncio
from pathlib import Path

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult
from quotacompass.core.config import AppConfig
from quotacompass.core.doctor import doctor_exit_code, run_doctor


class DeadEndpoint(Adapter):
    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "credentials available")

    async def fetch_usage(self):  # type: ignore[no-untyped-def]
        raise AdapterError("network_error", "endpoint unreachable", retryable=True)


class ExpiredEndpoint(Adapter):
    reauth_command = "provider login"

    async def probe(self) -> ProbeResult:
        return ProbeResult(True, "credentials available")

    async def fetch_usage(self):  # type: ignore[no-untyped-def]
        raise AdapterError("auth_expired", "credential expired")


def test_doctor_live_check_diagnoses_dead_endpoint(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"providers": {"dead": {"adapter": "manual"}}})

    checks = asyncio.run(run_doctor(config, tmp_path, [DeadEndpoint("dead")]))
    live = next(check for check in checks if check.id == "provider.dead.probe")

    assert not live.ok
    assert live.code == "network_error"
    assert "endpoint unreachable" in live.detail


def test_doctor_live_auth_expiry_returns_exit_four(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"providers": {"expired": {"adapter": "manual"}}})

    checks = asyncio.run(run_doctor(config, tmp_path, [ExpiredEndpoint("expired")]))

    assert doctor_exit_code(checks, tmp_path) == 4
    live = next(check for check in checks if check.id == "provider.expired.probe")
    assert "provider login" in live.hint

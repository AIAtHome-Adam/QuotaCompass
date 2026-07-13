from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from quotacompass.adapters.base import Adapter, AdapterError
from quotacompass.core.config import AppConfig, default_config_path
from quotacompass.core.discovery import credential_candidates, port_is_free
from quotacompass.core.models import AuthState, FetchState
from quotacompass.core.runtime import server_runtime
from quotacompass.core.statefile import read_snapshot


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    ok: bool
    detail: str
    hint: str
    code: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


async def run_doctor(
    config: AppConfig,
    state_dir: Path,
    adapters: list[Adapter],
    *,
    config_path: Path | None = None,
) -> list[DoctorCheck]:
    path = config_path or default_config_path()
    checks = [
        DoctorCheck("config.valid", True, str(path), "No action needed."),
        DoctorCheck(
            "state.directory",
            state_dir.parent.exists() or state_dir.exists(),
            str(state_dir),
            "Run `quotacompass setup --write` or create the parent directory.",
        ),
    ]

    reachable = server_runtime(state_dir) is not None
    checks.append(
        DoctorCheck(
            "service.liveness",
            reachable,
            f"{config.server.host}:{config.server.port} is {'reachable' if reachable else 'not reachable'}",
            "Start `quotacompass serve` or install the user service.",
        )
    )
    port_free = port_is_free(config.server.host, config.server.port)
    checks.append(
        DoctorCheck(
            "server.port",
            reachable or port_free,
            "occupied by the service" if reachable else ("available" if port_free else "occupied"),
            "Choose another port with `quotacompass setup`, or stop the conflicting process.",
        )
    )

    snapshot = read_snapshot(state_dir)
    if snapshot is None:
        checks.append(
            DoctorCheck(
                "state.freshness",
                False,
                "No current.json snapshot exists.",
                "Run `quotacompass poll` after configuring at least one provider.",
            )
        )
    else:
        now = datetime.now(UTC)
        stale = [
            provider.id
            for provider in snapshot.providers
            if provider.fetch_status != FetchState.OK or provider.stale_after <= now
        ]
        expired = [
            provider.id
            for provider in snapshot.providers
            if provider.auth.status == AuthState.EXPIRED
        ]
        detail = "fresh" if not stale and not expired else ", ".join(stale + expired)
        checks.append(
            DoctorCheck(
                "state.freshness",
                not stale and not expired,
                detail,
                "Run `quotacompass poll`; use `quotacompass reauth <id>` for expired auth.",
            )
        )

    candidates = credential_candidates()
    by_adapter: dict[str, list[Path]] = {}
    for candidate in candidates:
        if candidate.exists:
            by_adapter.setdefault(candidate.adapter, []).append(candidate.path)
    adapters_by_id = {adapter.provider_id: adapter for adapter in adapters}
    for provider_id, provider in config.providers.items():
        if not provider.enabled:
            continue
        paths = list(by_adapter.get(provider.adapter, []))
        configured_credentials = getattr(adapters_by_id.get(provider_id), "credentials", None)
        if configured_credentials and Path(configured_credentials).is_file():
            paths.insert(0, Path(configured_credentials))
        credentialless = provider.adapter in {"manual", "anthropic_api", "openrouter", "xai"}
        checks.append(
            DoctorCheck(
                f"provider.{provider_id}.credentials",
                credentialless or bool(paths),
                "not file-based" if credentialless else (str(paths[0]) if paths else "not found"),
                f"Sign in with the native {provider.adapter} tool, then rerun doctor.",
            )
        )

    async def probe(adapter: Adapter) -> DoctorCheck:
        try:
            result = await asyncio.wait_for(adapter.probe(), timeout=10)
            if not result.available:
                return DoctorCheck(
                    f"provider.{adapter.provider_id}.probe",
                    False,
                    result.detail,
                    "Check credentials, connectivity, and the provider verification notes.",
                    "prerequisite_missing",
                )
            await asyncio.wait_for(adapter.fetch_usage(), timeout=20)
            return DoctorCheck(
                f"provider.{adapter.provider_id}.probe",
                True,
                f"{result.detail}; live fetch succeeded",
                "No action needed.",
            )
        except AdapterError as exc:
            return DoctorCheck(
                f"provider.{adapter.provider_id}.probe",
                False,
                str(exc),
                (
                    f"Run {adapter.reauth_command}."
                    if exc.code == "auth_expired" and adapter.reauth_command
                    else "Check connectivity and docs/PROVIDERS.md, then retry."
                ),
                exc.code,
            )
        except TimeoutError:
            return DoctorCheck(
                f"provider.{adapter.provider_id}.probe",
                False,
                "live check timed out",
                "Check network access and provider status, then retry.",
                "timeout",
            )
        except Exception as exc:  # adapter boundary: diagnostics must continue
            return DoctorCheck(
                f"provider.{adapter.provider_id}.probe",
                False,
                f"{type(exc).__name__}: {exc}",
                "Check credentials and docs/PROVIDERS.md; other providers are unaffected.",
                "unexpected_error",
            )
        finally:
            await adapter.close()

    if adapters:
        checks.extend(await asyncio.gather(*(probe(adapter) for adapter in adapters)))
    return checks


def doctor_exit_code(checks: list[DoctorCheck], state_dir: Path) -> int:
    snapshot = read_snapshot(state_dir)
    if any(check.code == "auth_expired" for check in checks):
        return 4
    if snapshot and any(
        provider.auth.status == AuthState.EXPIRED for provider in snapshot.providers
    ):
        return 4
    return 0 if all(check.ok for check in checks) else 3

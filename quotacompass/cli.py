from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from quotacompass import __version__
from quotacompass.core.advisor import advise
from quotacompass.core.config import default_config_path, load_config, resolved_state_dir
from quotacompass.core.doctor import doctor_exit_code, run_doctor
from quotacompass.core.models import AuthState, FetchState, StateSnapshot
from quotacompass.core.reauth import ReauthManager
from quotacompass.core.runtime import request_server, server_runtime
from quotacompass.core.service import QuotaService
from quotacompass.core.statefile import read_snapshot, render_markdown
from quotacompass.setup_wizard import build_proposal, write_proposal


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, default=str))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quotacompass", description="Local-first AI quota advisor"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, help="Path to config.yaml")
    commands = parser.add_subparsers(dest="command", required=True)

    paths = commands.add_parser("paths", help="Show resolved config and state paths")
    paths.add_argument("--json", action="store_true")

    status = commands.add_parser("status", help="Read the latest quota snapshot")
    status.add_argument("--json", action="store_true")
    status.add_argument("--provider")
    status.add_argument("--poll", action="store_true", help="Request a fresh poll")
    status.add_argument(
        "--force",
        action="store_true",
        help="Poll directly even when the server is running (may duplicate provider requests)",
    )

    suggest = commands.add_parser("suggest", help="Show the current provider recommendation")
    suggest.add_argument("--json", action="store_true")
    suggest.add_argument("--task", choices=["agentic", "chat", "bulk"], default="agentic")

    nudges = commands.add_parser("nudges", help="Show quota that is close to resetting unused")
    nudges.add_argument("--json", action="store_true")

    poll = commands.add_parser("poll", help="Poll providers and update local state")
    poll.add_argument("--json", action="store_true")
    poll.add_argument(
        "--force",
        action="store_true",
        help="Poll directly even when the server is running (may duplicate provider requests)",
    )

    manual = commands.add_parser("set", help="Set a manual provider quota window")
    manual.add_argument("provider")
    manual.add_argument("--window", default="weekly")
    manual.add_argument("--used-pct", type=float)
    manual.add_argument("--resets-at")
    manual.add_argument("--cadence", help="For example: weekly:thu 23:59")
    manual.add_argument("--timezone", help="IANA timezone for cadence, e.g. America/Denver")
    manual.add_argument(
        "--quota-state",
        choices=["metered", "unlimited", "unknown", "unavailable"],
        default="metered",
    )

    reauth = commands.add_parser("reauth", help="Start a fixed provider login helper")
    reauth.add_argument("provider")

    serve = commands.add_parser("serve", help="Run the API and local dashboard")
    serve.add_argument("--demo", action="store_true", help="Use bundled synthetic data")
    serve.add_argument("--host", help="Override configured bind host")
    serve.add_argument("--port", type=int, help="Override configured bind port")

    doctor = commands.add_parser("doctor", help="Run local configuration and discovery checks")
    doctor.add_argument("--json", action="store_true")

    setup = commands.add_parser("setup", help="Inspect credentials and suggest a local port")
    setup.add_argument("--json", action="store_true")
    setup.add_argument("--write", action="store_true", help="Write the proposed config")
    setup.add_argument("--force", action="store_true", help="Replace an existing config")
    setup.add_argument("--non-interactive", action="store_true")
    return parser


def _exit_for_snapshot(snapshot: object) -> int:
    providers = getattr(snapshot, "providers", [])
    if any(provider.auth.status == AuthState.EXPIRED for provider in providers):
        return 4
    if any(provider.fetch_status in {FetchState.STALE, FetchState.ERROR} for provider in providers):
        return 3
    return 0


def _local_snapshot(state_dir: Path) -> StateSnapshot:
    snapshot = read_snapshot(state_dir)
    if snapshot is None:
        print("No state snapshot exists yet. Configure providers or run setup.", file=sys.stderr)
        raise SystemExit(3)
    return snapshot


def _coordinated_snapshot(config: object, state_dir: Path) -> StateSnapshot:
    runtime = server_runtime(state_dir)
    if runtime:
        try:
            return StateSnapshot.model_validate(
                request_server(runtime, "/api/v1/status", config)  # type: ignore[arg-type]
            )
        except (RuntimeError, ValidationError) as exc:
            print(f"Server query failed; using local state: {exc}", file=sys.stderr)
    return _local_snapshot(state_dir)


def _poll_snapshot(config: object, state_dir: Path, *, force: bool) -> StateSnapshot:
    runtime = server_runtime(state_dir)
    if runtime and not force:
        return StateSnapshot.model_validate(
            request_server(runtime, "/api/v1/poll", config, method="POST")  # type: ignore[arg-type]
        )
    if runtime and force:
        print(
            "Warning: --force bypasses the running server and may duplicate provider requests.",
            file=sys.stderr,
        )
    service = QuotaService(config, state_dir=state_dir)  # type: ignore[arg-type]
    if not service.adapters:
        print("No supported providers are configured.", file=sys.stderr)
        raise SystemExit(2)
    return asyncio.run(service.poll())


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    state_dir = resolved_state_dir(config)

    if args.command == "paths":
        result = {"config": str(args.config or default_config_path()), "state": str(state_dir)}
        if args.json:
            _json(result)
        else:
            print(f"Config: {result['config']}\nState: {result['state']}")
        return

    if args.command == "status":
        snapshot = (
            _poll_snapshot(config, state_dir, force=args.force)
            if args.poll
            else _coordinated_snapshot(config, state_dir)
        )
        if args.provider:
            snapshot.providers = [item for item in snapshot.providers if item.id == args.provider]
        output = snapshot.model_dump_json(indent=2) if args.json else render_markdown(snapshot)
        print(output, end="\n")
        raise SystemExit(_exit_for_snapshot(snapshot))

    if args.command in {"suggest", "nudges"}:
        snapshot = _coordinated_snapshot(config, state_dir)
        advisor = (
            advise(snapshot.providers, config.advisor, task=args.task)
            if args.command == "suggest"
            else snapshot.advisor
        )
        value = (
            advisor.model_dump(mode="json")
            if args.command == "suggest"
            else [item.model_dump(mode="json") for item in advisor.expiring_unused]
        )
        if args.json:
            _json(value)
        elif args.command == "suggest":
            print(advisor.suggestion or "No provider is currently recommendable.")
            for item in advisor.ranking:
                print(f"{item.id}: {item.score:.3f} — {item.reason}")
        elif value:
            for item in advisor.expiring_unused:
                print(
                    f"{item.id} {item.window}: {item.unused_pct:.0f}% unused; resets {item.resets_at}"
                )
        else:
            print("No quota windows currently need a pre-reset nudge.")
        raise SystemExit(_exit_for_snapshot(snapshot))

    if args.command == "poll":
        snapshot = _poll_snapshot(config, state_dir, force=args.force)
        output = snapshot.model_dump_json(indent=2) if args.json else render_markdown(snapshot)
        print(output, end="\n")
        raise SystemExit(_exit_for_snapshot(snapshot))

    if args.command == "set":
        if args.quota_state == "metered" and args.used_pct is None:
            print("--used-pct is required for a metered window.", file=sys.stderr)
            raise SystemExit(2)
        if args.resets_at and args.cadence:
            print("Use either --resets-at or --cadence, not both.", file=sys.stderr)
            raise SystemExit(2)
        service = QuotaService(config, state_dir=state_dir)
        window = {
            "name": args.window,
            "quota_state": args.quota_state,
            "used_pct": args.used_pct,
            "resets_at": args.resets_at,
            "cadence": args.cadence,
            "timezone": args.timezone or config.timezone,
            "estimated": True,
        }
        snapshot = asyncio.run(service.set_manual(args.provider, [window]))
        print(render_markdown(snapshot), end="")
        return

    if args.command == "reauth":
        manager = ReauthManager(config, state_dir)
        try:
            result = manager.start(args.provider, origin="cli")
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            print(f"Reauthentication failed: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        _json(result)
        return

    if args.command == "serve":
        import uvicorn

        from quotacompass.server.app import create_app

        host = args.host or config.server.host
        port = args.port or config.server.port
        if host not in {"127.0.0.1", "localhost", "::1"} and not config.server.auth_token:
            print("A non-loopback bind requires server.auth_token.", file=sys.stderr)
            raise SystemExit(2)
        effective = config.model_copy(deep=True)
        effective.server.host = host
        effective.server.port = port
        uvicorn.run(create_app(effective, demo=args.demo), host=host, port=port)
        return

    if args.command == "setup":
        proposal = build_proposal(config_path=args.config)
        should_write = args.write
        if not args.non_interactive and not args.write and sys.stdin.isatty():
            print(yaml.safe_dump(proposal.as_dict(), sort_keys=False, allow_unicode=True))
            should_write = input("Write this configuration? [y/N] ").strip().lower() == "y"
        if should_write:
            try:
                written = write_proposal(proposal, overwrite=args.force)
            except FileExistsError as exc:
                print(str(exc), file=sys.stderr)
                raise SystemExit(2) from exc
            configured = load_config(written)
            configured_state = resolved_state_dir(configured)
            service = QuotaService(configured, state_dir=configured_state)
            checks = asyncio.run(
                run_doctor(configured, configured_state, service.adapters, config_path=written)
            )
            result = proposal.as_dict() | {
                "written": str(written),
                "doctor": [check.as_dict() for check in checks],
            }
        else:
            result = proposal.as_dict() | {"written": None}
        if args.json:
            _json(result)
        else:
            print(yaml.safe_dump(result, sort_keys=False, allow_unicode=True))
        return

    if args.command == "doctor":
        service = QuotaService(config, state_dir=state_dir)
        checks = asyncio.run(
            run_doctor(config, state_dir, service.adapters, config_path=args.config)
        )
        if args.json:
            _json({"checks": [check.as_dict() for check in checks]})
        else:
            for check in checks:
                print(f"{'PASS' if check.ok else 'FAIL'} {check.id}: {check.detail}")
                if not check.ok:
                    print(f"     Fix: {check.hint}")
        raise SystemExit(doctor_exit_code(checks, state_dir))


if __name__ == "__main__":
    main()

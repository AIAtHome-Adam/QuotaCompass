from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from quotacompass.adapters.base import Adapter, AdapterError, ProbeResult
from quotacompass.core.models import (
    AuthState,
    AuthStatus,
    DataSource,
    LimitWindow,
    ProviderStatus,
    QuotaState,
    ReauthHint,
    SupportTier,
)

WINDOWS = (
    ("5h", timedelta(hours=5), 12.0),
    ("weekly", timedelta(days=7), 30.0),
    ("monthly", timedelta(days=30), 60.0),
)


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def _message_cost_and_time(payload: dict[str, Any]) -> tuple[float | None, datetime | None]:
    cost = payload.get("cost")
    if not isinstance(cost, (int, float)):
        cost = (payload.get("usage") or {}).get("cost")
    time_value = payload.get("created_at") or payload.get("createdAt")
    if time_value is None:
        time_value = (payload.get("time") or {}).get("created")
    return (float(cost) if isinstance(cost, (int, float)) else None, _timestamp(time_value))


class OpenCodeAdapter(Adapter):
    default_support_tier = SupportTier.BETA
    default_data_source = DataSource.LOCAL_DERIVED
    reauth_command = "opencode auth login"
    reauth_automatable = True

    def __init__(self, provider_id: str, options: dict[str, Any] | None = None) -> None:
        super().__init__(provider_id, options)
        configured = self.options.get("state_db") or self.options.get("database")
        self.database = (
            Path(configured).expanduser()
            if configured
            else Path.home() / ".local" / "share" / "opencode" / "opencode.db"
        )
        auth = self.options.get("credentials")
        self.credentials = (
            Path(auth).expanduser()
            if auth
            else Path.home() / ".local" / "share" / "opencode" / "auth.json"
        )

    async def probe(self) -> ProbeResult:
        return ProbeResult(self.database.is_file(), str(self.database))

    def _events(self) -> list[tuple[datetime, float]]:
        try:
            connection = sqlite3.connect(f"file:{self.database.as_posix()}?mode=ro", uri=True)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "message" not in tables:
                    raise AdapterError("schema_changed", "OpenCode database has no message table")
                columns = {row[1] for row in connection.execute("PRAGMA table_info(message)")}
                events: list[tuple[datetime, float]] = []
                if {"cost", "created_at"}.issubset(columns):
                    for cost, created in connection.execute(
                        "SELECT cost, created_at FROM message WHERE cost IS NOT NULL"
                    ):
                        timestamp = _timestamp(created)
                        if timestamp and isinstance(cost, (int, float)):
                            events.append((timestamp, float(cost)))
                    return events
                data_column = "data" if "data" in columns else "json" if "json" in columns else None
                if not data_column:
                    raise AdapterError(
                        "schema_changed", "OpenCode message table has no supported payload column"
                    )
                for (raw,) in connection.execute(f"SELECT {data_column} FROM message"):
                    try:
                        payload = json.loads(raw) if isinstance(raw, str) else raw
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    cost, timestamp = _message_cost_and_time(payload)
                    if cost is not None and timestamp is not None:
                        events.append((timestamp, cost))
                return events
            finally:
                connection.close()
        except AdapterError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise AdapterError(
                "database_unreadable", f"OpenCode database is unavailable: {exc}"
            ) from exc

    async def fetch_usage(self) -> ProviderStatus:
        now = datetime.now(UTC)
        events = self._events()
        windows: list[LimitWindow] = []
        raw_spend: dict[str, float] = {}
        for name, duration, cap in WINDOWS:
            start = now - duration
            relevant = [(timestamp, cost) for timestamp, cost in events if timestamp >= start]
            spent = sum(cost for _, cost in relevant)
            raw_spend[name] = round(spent, 6)
            next_recovery = min((timestamp + duration for timestamp, _ in relevant), default=None)
            windows.append(
                LimitWindow(
                    window_id=f"{self.provider_id}:{name}",
                    name=name,
                    quota_state=QuotaState.METERED,
                    used_pct=max(0.0, min(100.0, spent / cap * 100)),
                    resets_at=next_recovery,
                    window_duration_seconds=int(duration.total_seconds()),
                    estimated=True,
                )
            )
        auth_status = AuthState.OK if self.credentials.exists() else AuthState.UNKNOWN
        return ProviderStatus(
            id=self.provider_id,
            label=self.label,
            kind="subscription",
            support_tier=self.support_tier,
            data_source=self.data_source,
            auth=AuthStatus(
                status=auth_status,
                source=str(self.credentials),
                reauth=ReauthHint(command=self.reauth_command, automatable=True),
            ),
            windows=windows,
            raw_extras={
                "spend_usd": raw_spend,
                "caps_usd": {name: cap for name, _, cap in WINDOWS},
                "source_events": len(events),
            },
            fetched_at=now,
            last_success_at=now,
            stale_after=now + timedelta(minutes=30),
        )

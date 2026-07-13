from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotacompass.core.models import ProviderStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_snapshots (
    provider_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (provider_id, fetched_at)
);
CREATE INDEX IF NOT EXISTS idx_provider_snapshots_time
ON provider_snapshots(provider_id, fetched_at DESC);
"""


class HistoryStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(SCHEMA)

    def add(self, provider: ProviderStatus) -> None:
        payload = json.dumps(provider.model_dump(mode="json"), separators=(",", ":"))
        self.connection.execute(
            "INSERT OR REPLACE INTO provider_snapshots VALUES (?, ?, ?)",
            (provider.id, provider.fetched_at.isoformat(), payload),
        )
        self.connection.commit()

    def history(self, provider_id: str, *, days: int = 30) -> list[ProviderStatus]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        rows = self.connection.execute(
            "SELECT payload_json FROM provider_snapshots "
            "WHERE provider_id = ? AND fetched_at >= ? ORDER BY fetched_at",
            (provider_id, cutoff),
        ).fetchall()
        return [ProviderStatus.model_validate_json(row[0]) for row in rows]

    def prune(self, retention_days: int) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        cursor = self.connection.execute(
            "DELETE FROM provider_snapshots WHERE fetched_at < ?", (cutoff,)
        )
        self.connection.commit()
        return cursor.rowcount

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

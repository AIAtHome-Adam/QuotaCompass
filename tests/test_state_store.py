from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotacompass.core.models import DataSource, ProviderStatus, StateSnapshot, SupportTier
from quotacompass.core.statefile import read_snapshot, write_snapshot
from quotacompass.core.store import HistoryStore


def sample() -> ProviderStatus:
    now = datetime.now(UTC)
    return ProviderStatus(
        id="sample",
        label="Sample",
        kind="manual",
        support_tier=SupportTier.STABLE,
        data_source=DataSource.MANUAL,
        fetched_at=now,
        last_success_at=now,
        stale_after=now + timedelta(hours=1),
    )


def test_atomic_snapshot_round_trip(tmp_path: Path) -> None:
    snapshot = StateSnapshot(providers=[sample()])
    json_path, markdown_path = write_snapshot(tmp_path, snapshot)
    assert json_path.exists() and markdown_path.exists()
    assert read_snapshot(tmp_path) == snapshot
    assert "Sample" in markdown_path.read_text(encoding="utf-8")


def test_history_round_trip(tmp_path: Path) -> None:
    item = sample()
    with HistoryStore(tmp_path / "history.sqlite3") as store:
        store.add(item)
        assert store.history("sample") == [item]

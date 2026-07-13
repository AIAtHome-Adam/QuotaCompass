from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quotacompass.adapters.base import Adapter
from quotacompass.adapters.manual import ManualAdapter
from quotacompass.adapters.registry import configured_adapters
from quotacompass.core.advisor import advise
from quotacompass.core.config import AppConfig, resolved_state_dir
from quotacompass.core.manual_store import ManualEntryStore
from quotacompass.core.models import FetchState, ProviderStatus, StateSnapshot
from quotacompass.core.poller import poll_adapters
from quotacompass.core.statefile import read_snapshot, write_snapshot
from quotacompass.core.store import HistoryStore


def merge_last_known_good(
    current: list[ProviderStatus], previous: StateSnapshot | None
) -> list[ProviderStatus]:
    """Retain old usage windows when a provider fails, while preserving the new failure."""
    if previous is None:
        return current
    old_by_id = {provider.id: provider for provider in previous.providers}
    merged: list[ProviderStatus] = []
    for provider in current:
        old = old_by_id.get(provider.id)
        if provider.fetch_status == FetchState.ERROR and old and old.last_success_at:
            provider.windows = old.windows
            provider.raw_extras = old.raw_extras
            provider.last_success_at = old.last_success_at
            provider.fetch_status = FetchState.STALE
            if provider.auth.status == "unknown":
                provider.auth = old.auth
        merged.append(provider)
    return merged


class QuotaService:
    def __init__(
        self,
        config: AppConfig,
        *,
        state_dir: Path | None = None,
        adapters: list[Adapter] | None = None,
    ) -> None:
        self.config = config
        self.state_dir = state_dir or resolved_state_dir(config)
        self.adapters = adapters if adapters is not None else configured_adapters(config)
        self.manual_entries = ManualEntryStore(self.state_dir)
        self._poll_lock = asyncio.Lock()

    def current(self) -> StateSnapshot | None:
        return read_snapshot(self.state_dir)

    def _apply_manual_entries(self) -> None:
        values = self.manual_entries.load()
        for adapter in self.adapters:
            if isinstance(adapter, ManualAdapter) and adapter.provider_id in values:
                adapter.options["windows"] = values[adapter.provider_id]

    async def poll(self) -> StateSnapshot:
        async with self._poll_lock:
            self._apply_manual_entries()
            previous = self.current()
            providers = await poll_adapters(
                self.adapters,
                concurrency=self.config.poll.concurrency,
            )
            providers = merge_last_known_good(providers, previous)
            providers = await self._apply_manual_fallbacks(providers)
            return self._persist(providers)

    async def _apply_manual_fallbacks(
        self, providers: list[ProviderStatus]
    ) -> list[ProviderStatus]:
        values = self.manual_entries.load()
        for provider in providers:
            windows = values.get(provider.id)
            if not windows or provider.fetch_status == FetchState.OK:
                continue
            manual = await ManualAdapter(
                provider.id,
                {
                    "label": provider.label,
                    "windows": windows,
                    "timezone": self.config.timezone,
                },
            ).fetch_usage()
            provider.windows = manual.windows
            provider.data_source = manual.data_source
            provider.last_success_at = manual.last_success_at
            provider.stale_after = manual.stale_after
            provider.raw_extras["manual_fallback"] = True
        return providers

    def _persist(self, providers: list[ProviderStatus]) -> StateSnapshot:
        for provider in providers:
            configured = self.config.providers.get(provider.id)
            if configured:
                provider.raw_extras["priority"] = configured.priority
                if configured.linked_account:
                    provider.raw_extras["linked_account"] = configured.linked_account
        snapshot = StateSnapshot(
            generated_at=datetime.now(UTC),
            providers=providers,
            advisor=advise(providers, self.config.advisor),
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with HistoryStore(self.state_dir / "history.sqlite3") as store:
            for provider in providers:
                if provider.fetch_status == FetchState.OK:
                    store.add(provider)
            store.prune(self.config.state.history_retention_days)
        write_snapshot(self.state_dir, snapshot)
        return snapshot

    async def set_manual(self, provider_id: str, windows: list[dict[str, Any]]) -> StateSnapshot:
        async with self._poll_lock:
            return await self._set_manual(provider_id, windows)

    async def _set_manual(self, provider_id: str, windows: list[dict[str, Any]]) -> StateSnapshot:
        self.manual_entries.set(provider_id, windows)
        configured = next(
            (
                adapter
                for adapter in self.adapters
                if adapter.provider_id == provider_id and isinstance(adapter, ManualAdapter)
            ),
            None,
        )
        adapter = configured or ManualAdapter(
            provider_id, {"label": provider_id, "windows": windows}
        )
        adapter.options["windows"] = windows
        manual = await adapter.fetch_usage()
        current = self.current()
        providers = (
            []
            if current is None
            else [provider for provider in current.providers if provider.id != provider_id]
        )
        providers.append(manual)
        return self._persist(providers)

    def history(self, provider_id: str, days: int = 30) -> list[ProviderStatus]:
        path = self.state_dir / "history.sqlite3"
        if not path.exists():
            return []
        with HistoryStore(path) as store:
            return store.history(provider_id, days=days)

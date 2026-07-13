import os
from pathlib import Path

import pytest

import quotacompass.core.runtime as runtime_module
from quotacompass.core.runtime import pidfile_path, remove_pidfile, server_runtime, write_pidfile


def test_pidfile_requires_owner_process_and_reachable_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        runtime_module.socket,
        "create_connection",
        lambda *_args, **_kwargs: Connection(),
    )
    write_pidfile(tmp_path, "127.0.0.1", 54790)

    running = server_runtime(tmp_path)

    assert running and running["pid"] == os.getpid()
    assert running["port"] == 54790
    monkeypatch.setattr(runtime_module, "_pid_exists", lambda _pid: False)
    assert server_runtime(tmp_path) is None
    remove_pidfile(tmp_path)
    assert not pidfile_path(tmp_path).exists()

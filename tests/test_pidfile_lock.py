from pathlib import Path

import pytest

import quotacompass.core.runtime as runtime


def test_pidfile_rejects_second_live_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        runtime,
        "server_runtime",
        lambda _state: {"pid": 99999, "host": "127.0.0.1", "port": 4747},
    )

    with pytest.raises(RuntimeError, match="already runs"):
        runtime.write_pidfile(tmp_path, "127.0.0.1", 4748)

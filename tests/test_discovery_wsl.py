from types import SimpleNamespace

import psutil

import quotacompass.core.discovery as discovery
from quotacompass.core.discovery import (
    _decode_wsl_output,
    _parse_ss_listening_ports,
    native_listening_ports,
    wsl_listening_ports,
    wsl_unc_path,
)


def test_utf16_wsl_listing_decode() -> None:
    payload = "Ubuntu\r\nDebian\r\n".encode("utf-16-le")
    assert _decode_wsl_output(payload).splitlines() == ["Ubuntu", "Debian"]


def test_wsl_unc_path() -> None:
    path = wsl_unc_path("Ubuntu", "/home/example/.codex/auth.json")
    normalized = str(path).replace("\\", "/")
    assert normalized.endswith("wsl.localhost/Ubuntu/home/example/.codex/auth.json")

def test_parse_ss_listening_ports_handles_ipv4_ipv6_and_wildcards() -> None:
    output = "\n".join(
        [
            "LISTEN 0 4096 127.0.0.1:4747 0.0.0.0:*",
            "LISTEN 0 128 [::]:9119 [::]:*",
            "LISTEN 0 64 *:18789 *:*",
        ]
    )
    assert _parse_ss_listening_ports(output) == {4747, 9119, 18789}


def test_native_listening_ports_filters_to_tcp_listeners(monkeypatch) -> None:
    connections = [
        SimpleNamespace(status=psutil.CONN_LISTEN, laddr=SimpleNamespace(port=4747)),
        SimpleNamespace(status="ESTABLISHED", laddr=SimpleNamespace(port=9000)),
        SimpleNamespace(status=psutil.CONN_LISTEN, laddr=()),
    ]
    monkeypatch.setattr(discovery.psutil, "net_connections", lambda **_kwargs: connections)
    assert native_listening_ports() == {4747}


def test_wsl_listening_ports_uses_bounded_numeric_ss(monkeypatch) -> None:
    result = SimpleNamespace(
        stdout=b"LISTEN 0 4096 0.0.0.0:9119 0.0.0.0:*\n",
    )
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(discovery.subprocess, "run", run)
    assert wsl_listening_ports("Ubuntu") == {9119}
    assert calls[0][0] == ["wsl.exe", "-d", "Ubuntu", "--", "ss", "-H", "-ltn"]
    assert calls[0][1]["timeout"] == 8

#!/usr/bin/env python3
"""Resolve QuotaCompass data via CLI, REST, then its local state file."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def from_cli(command: str) -> object | None:
    executable = shutil.which("quotacompass")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, command, "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.stdout.strip() and result.returncode in {0, 3, 4}:
            return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    return None


def from_rest(command: str, base_url: str, token: str | None) -> object | None:
    endpoint = {"status": "status", "suggest": "suggest", "nudges": "nudges"}[command]
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/v1/{endpoint}")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def state_candidates(explicit: str | None) -> list[Path]:
    values = [explicit, os.getenv("QUOTACOMPASS_STATE_FILE")]
    if os.name == "nt":
        local = os.getenv("LOCALAPPDATA")
        if local:
            values.append(str(Path(local) / "quotacompass" / "current.json"))
    else:
        values.extend(
            [
                str(Path.home() / ".local" / "state" / "quotacompass" / "current.json"),
                str(
                    Path.home()
                    / "Library"
                    / "Application Support"
                    / "quotacompass"
                    / "current.json"
                ),
            ]
        )
    return [Path(value).expanduser() for value in values if value]


def from_state(command: str, explicit: str | None) -> object | None:
    for path in state_candidates(explicit):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if command == "status":
            return snapshot
        advisor = snapshot.get("advisor", {})
        return advisor if command == "suggest" else advisor.get("expiring_unused", [])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "suggest", "nudges"])
    parser.add_argument("--url", default=os.getenv("QUOTACOMPASS_URL", "http://127.0.0.1:4747"))
    parser.add_argument("--state-file")
    args = parser.parse_args()
    value = from_cli(args.command)
    if value is None:
        value = from_rest(args.command, args.url, os.getenv("QUOTACOMPASS_TOKEN"))
    if value is None:
        value = from_state(args.command, args.state_file)
    if value is None:
        print(
            "QuotaCompass is unavailable via CLI, REST, and state file; run `quotacompass doctor`.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

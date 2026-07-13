"""Development spike: show redacted Hermes portal output shape."""

from __future__ import annotations

import re
import subprocess


def main() -> None:
    result = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu", "--", "sh", "-lc", "hermes portal info"],
        capture_output=True,
        timeout=30,
    )
    output = (result.stdout + result.stderr).decode(errors="replace")
    output = re.sub(r"[\w.+-]+@[\w.-]+", "<redacted-email>", output)
    output = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "<redacted-secret>", output)
    print(f"exit={result.returncode}")
    print(output.encode("ascii", "backslashreplace").decode())


if __name__ == "__main__":
    main()

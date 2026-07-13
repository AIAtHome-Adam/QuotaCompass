from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TARGETS = ("hermes", "openclaw")


def build() -> None:
    body = (ROOT / "shared" / "BODY.md").read_text(encoding="utf-8").strip()
    script = ROOT / "shared" / "scripts" / "query.py"
    for target in TARGETS:
        destination = ROOT / target / "quotacompass"
        scripts = destination / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        frontmatter = (ROOT / "frontmatter" / f"{target}.md").read_text(encoding="utf-8").strip()
        (destination / "SKILL.md").write_text(f"{frontmatter}\n\n{body}\n", encoding="utf-8")
        shutil.copy2(script, scripts / "query.py")


if __name__ == "__main__":
    build()

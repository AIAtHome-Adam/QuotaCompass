import re
from pathlib import Path


def test_dashboard_has_no_external_runtime_or_telemetry_reference() -> None:
    static = Path(__file__).parents[1] / "quotacompass" / "server" / "static"
    content = b"".join(
        path.read_bytes().lower()
        for path in static.rglob("*")
        if path.suffix in {".html", ".css", ".js"}
    )
    for forbidden in (
        b"fonts.googleapis.com",
        b"posthog",
        b"sentry",
        b"google-analytics.com",
    ):
        assert forbidden not in content


def test_dashboard_asset_references_resolve_and_conflicts_are_excluded() -> None:
    root = Path(__file__).parents[1]
    static = root / "quotacompass" / "server" / "static"
    index = (static / "index.html").read_text(encoding="utf-8")
    assets = re.findall(r'["\']/(assets/[^"\']+)["\']', index)

    assert assets
    for asset in assets:
        assert (static / asset).is_file(), asset

    packaging = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert packaging.count("/**/*# Name clash*") == 2

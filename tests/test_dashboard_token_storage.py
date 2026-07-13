from pathlib import Path


def test_dashboard_api_token_is_session_only() -> None:
    source = (Path(__file__).parents[1] / "web" / "src" / "api.ts").read_text(encoding="utf-8")

    assert "sessionStorage" in source
    assert "localStorage" not in source
    assert "Authorization" in source

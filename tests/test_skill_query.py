import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "skills" / "shared" / "scripts" / "query.py"


def load_query_module():
    spec = importlib.util.spec_from_file_location("quotacompass_skill_query", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_query_reads_state_fallback(tmp_path: Path) -> None:
    state = {
        "schema_version": 1,
        "generated_at": "2026-07-11T00:00:00+00:00",
        "providers": [],
        "advisor": {"suggestion": "codex", "ranking": [], "expiring_unused": []},
    }
    path = tmp_path / "current.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    query = load_query_module()

    assert query.from_state("status", str(path)) == state
    assert query.from_state("suggest", str(path))["suggestion"] == "codex"
    assert query.from_state("nudges", str(path)) == []


def test_generated_skills_share_body_and_script() -> None:
    root = Path(__file__).parents[1] / "skills"
    body = (root / "shared" / "BODY.md").read_text(encoding="utf-8").strip()
    script = (root / "shared" / "scripts" / "query.py").read_bytes()
    for target in ("hermes", "openclaw"):
        generated = root / target / "quotacompass"
        assert (generated / "SKILL.md").read_text(encoding="utf-8").endswith(body + "\n")
        assert (generated / "scripts" / "query.py").read_bytes() == script


def test_hermes_skill_declares_terminal_and_uses_absolute_skill_path() -> None:
    root = Path(__file__).parents[1] / "skills"
    source = (root / "frontmatter" / "hermes.md").read_text(encoding="utf-8")
    generated = (root / "hermes" / "quotacompass" / "SKILL.md").read_text(encoding="utf-8")

    assert "requires_toolsets: [terminal]" in source
    assert "requires_toolsets: [terminal]" in generated
    assert "${HERMES_SKILL_DIR}/scripts/query.py" in generated

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_package_declares_modern_mit_metadata_without_account_email() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    metadata = project["project"]

    assert metadata["license"] == "MIT"
    assert metadata["license-files"] == ["LICENSE"]
    assert "License :: OSI Approved :: MIT License" not in metadata["classifiers"]
    assert all("email" not in author for author in metadata["authors"])
    assert any(
        requirement.startswith("hatchling>=1.27")
        for requirement in project["build-system"]["requires"]
    )


def test_publish_workflow_keeps_test_and_production_boundaries() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish.yml").read_text(
        encoding="utf-8"
    )

    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert (
        "if: github.event_name == 'release' && "
        "github.event.release.prerelease == false"
    ) in workflow
    assert "repository-url: https://test.pypi.org/legacy/" in workflow
    assert "name: testpypi" in workflow
    assert "name: pypi" in workflow
    assert workflow.count("id-token: write") == 2
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "password:" not in workflow
    assert "api-token:" not in workflow
    assert "${{ secrets." not in workflow

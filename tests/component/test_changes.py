import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        "check_changes", ROOT / "scripts/check_changes.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path):
    shutil.copy(ROOT / "pyproject.toml", tmp_path)
    shutil.copytree(ROOT / "scripts/templates", tmp_path / "scripts/templates")
    (tmp_path / "changes").mkdir()
    (tmp_path / "changes/README.md").write_text("Instructions")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n<!-- towncrier release notes start -->\n\n"
        "## [0.9.0] - 2026-09-09\n\n- Historical note.\n"
    )
    return tmp_path


def test_fragment_validation_handles_empty_invalid_and_internal(project):
    (project / "changes/+empty.added.md").touch()
    (project / "changes/wrong.xyz.md").write_text("Unknown type")
    (project / "changes/+tests.internal.md").write_text("Only reorganizes tests.")
    errors = load().check(project)
    assert len(errors) == 2
    assert any("+empty.added.md" in error for error in errors)
    assert any("wrong.xyz.md" in error for error in errors)


def test_towncrier_preview_and_build_preserve_history_consume_notes(project):
    pytest.importorskip("towncrier")
    (project / "changes/+feature.added.md").write_text("Add a dataset.")
    (project / "changes/+tests.internal.md").write_text("Only reorganizes tests.")
    for args in [
        ["init", "-b", "main"],
        ["config", "user.name", "Test"],
        ["config", "user.email", "test@example.invalid"],
        ["config", "core.hooksPath", "/dev/null"],
        ["add", "."],
        ["commit", "-m", "pending changes"],
    ]:
        subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)
    original = (project / "CHANGELOG.md").read_bytes()
    preview = load().preview(project)
    assert "Add a dataset." in preview and "Only reorganizes" not in preview
    assert "vUnreleased" not in preview
    assert (project / "CHANGELOG.md").read_bytes() == original
    assert len(load().fragment_paths(project)) == 2
    subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "build",
            "--yes",
            "--version",
            "0.10.0",
            "--date",
            "2026-09-09",
        ],
        cwd=project,
        check=True,
        capture_output=True,
    )
    built = (project / "CHANGELOG.md").read_bytes()
    assert built.endswith(original[original.index(b"## [0.9.0]") :])
    assert b"## [0.10.0](https://github.com/jakeryderv/usdata/releases/tag/v0.10.0)" in built
    assert b"Add a dataset." in built and b"Only reorganizes" not in built
    assert not load().fragment_paths(project)
    assert load().preview(project) == "No public changes pending."

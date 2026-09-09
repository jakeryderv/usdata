import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def script(name, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "core.hooksPath", "/dev/null")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.9.0"\n')
    (tmp_path / "README.md").write_text("Available from source for v0.10.")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [0.9.0] - 2026-09-09\n\n- Feature\n"
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def test_release_failure_preserves_main_and_prepared_work(repository, monkeypatch):
    module = script("release", monkeypatch)
    original = module.run

    def commands(root, *command):
        if command == ("git", "pull", "--ff-only"):
            return ""
        if command[:2] == ("uv", "version"):
            (root / "pyproject.toml").write_text('[project]\nversion="0.10.0"\n')
            return ""
        if command[0] == "uv":
            raise subprocess.CalledProcessError(1, command, stderr="empty changelog")
        return original(root, *command)

    monkeypatch.setattr(module, "run", commands)
    with pytest.raises(subprocess.CalledProcessError):
        module.prepare(repository, "minor")
    assert git(repository, "branch", "--show-current") == "release/v0.10.0"
    assert 'version="0.9.0"' in git(repository, "show", "main:pyproject.toml")
    assert 'version="0.10.0"' in (repository / "pyproject.toml").read_text()
    assert git(repository, "status", "--porcelain")


def test_release_refuses_untracked_files_before_preparation(repository, monkeypatch):
    module = script("release", monkeypatch)
    (repository / "notes.txt").touch()
    with pytest.raises(ValueError, match="untracked"):
        module.prepare(repository, "minor")
    assert git(repository, "branch", "--show-current") == "main"


def test_failed_release_gate_never_pushes_or_creates_pr(repository, monkeypatch):
    module = script("release", monkeypatch)
    git(repository, "switch", "-c", "release/v0.9.0")
    calls = []
    original = subprocess.run

    def commands(command, **kwargs):
        calls.append(command)
        if command == ["just", "check"]:
            raise subprocess.CalledProcessError(1, command)
        return original(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", commands)
    with pytest.raises(subprocess.CalledProcessError):
        module.open_pr(repository)
    assert not any("push" in command or "gh" in command or "commit" in command for command in calls)


@pytest.mark.parametrize(
    "changed",
    ["clean", "dirty", "new-commit", "unmerged", "ignored-lock", "ignored-data", "tool-cache"],
)
def test_cleanup_requires_exact_merged_tip_and_clean_worktree(repository, monkeypatch, changed):
    module = script("cleanup_pr", monkeypatch)
    (repository / ".gitignore").write_text("*.lock.json\nlocal-data/\n.venv/\n")
    git(repository, "add", ".gitignore")
    git(repository, "commit", "-m", "ignore generated files")
    git(repository, "switch", "-c", "feat/example")
    (repository / "feature.txt").write_text("feature")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "feature")
    tip = git(repository, "rev-parse", "HEAD")
    git(repository, "switch", "main")
    git(repository, "merge", "--squash", "feat/example")
    git(repository, "commit", "-m", "squashed feature")
    merged = git(repository, "rev-parse", "HEAD")
    git(repository, "update-ref", "refs/remotes/origin/main", merged)
    worktree = repository.with_name(repository.name + "-topic")
    git(repository, "worktree", "add", str(worktree), "feat/example")
    if changed in {"dirty", "new-commit"}:
        (worktree / "notes.txt").write_text("retain this")
        if changed == "new-commit":
            git(worktree, "add", ".")
            git(worktree, "commit", "-m", "extra work")
    if changed == "ignored-lock":
        (worktree / "dataset.lock.json").write_text("pinned inputs")
    if changed in {"ignored-data", "tool-cache"}:
        directory = worktree / ("local-data" if changed == "ignored-data" else ".venv")
        directory.mkdir()
        (directory / "file").write_text("bytes")
    original = module.run

    def commands(root, *command):
        if command[0] == "gh":
            return json.dumps(
                {
                    "state": "OPEN" if changed == "unmerged" else "MERGED",
                    "baseRefName": "main",
                    "headRefName": "feat/example",
                    "headRefOid": tip,
                    "mergeCommit": {"oid": merged},
                    "isCrossRepository": False,
                }
            )
        if command[:2] == ("git", "fetch"):
            return ""
        return original(root, *command)

    monkeypatch.setattr(module, "run", commands)
    if changed in {"clean", "tool-cache"}:
        module.cleanup(repository, "123")
        assert not worktree.exists()
        assert "feat/example" not in git(repository, "branch", "--list")
    else:
        with pytest.raises(ValueError):
            module.cleanup(repository, "123")
        assert worktree.exists()
        assert "feat/example" in git(repository, "branch", "--list")


@pytest.mark.parametrize(
    "body",
    [
        "## [Unreleased]\n- Pending\n## [0.9.0] - 2026-09-09\n- Old",
        "## [Unreleased]\n## [0.8.0] - 2026-09-09\n- Wrong version",
        "## [Unreleased]\n## [0.9.0]\n- Undated",
    ],
)
def test_release_pr_refuses_incomplete_changelog_roll(repository, monkeypatch, body):
    module = script("release", monkeypatch)
    git(repository, "switch", "-c", "release/v0.9.0")
    (repository / "CHANGELOG.md").write_text(body)
    with pytest.raises(ValueError, match="roll the changelog"):
        module.open_pr(repository)


def test_validated_release_opens_draft_without_enabling_merge(repository, monkeypatch):
    module = script("release", monkeypatch)
    git(repository, "switch", "-c", "release/v0.9.0")
    calls = []
    original = subprocess.run

    def commands(command, **kwargs):
        calls.append(tuple(command))
        if command[0] == "gh" or "push" in command or command == ["just", "check"]:
            return subprocess.CompletedProcess(
                command, 0, stdout="https://example.invalid/pr", stderr=""
            )
        return original(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", commands)
    module.open_pr(repository)
    create = next(command for command in calls if command[:3] == ("gh", "pr", "create"))
    assert "--draft" in create
    assert calls.index(("just", "check")) < calls.index(create)
    assert not any("merge" in command or "--auto" in command for command in calls)

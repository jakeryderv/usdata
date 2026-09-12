"""Prepare a release on a branch, then validate and open its draft PR."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from changelog import parse
from check_changes import fragment_paths
from check_release_docs import check

ROOT = Path(__file__).resolve().parents[1]


def run(root: Path, *command: str) -> str:
    return subprocess.run(
        command, cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def version(root: Path) -> str:
    return tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]


def prepare(root: Path, bump: str) -> None:
    if bump not in {"patch", "minor", "major"}:
        raise ValueError("bump must be patch, minor, or major")
    if run(root, "git", "branch", "--show-current") != "main":
        raise ValueError("start release preparation from main")
    if run(root, "git", "status", "--porcelain"):
        raise ValueError("working tree must be clean, including untracked files")
    run(root, "git", "pull", "--ff-only")
    if not any(".internal." not in path.name for path in fragment_paths(root)):
        raise ValueError("no public release notes; add a changes fragment before releasing")
    current = version(root)
    if not re.fullmatch(r"\d+\.\d+\.\d+", current):
        raise ValueError(f"expected a stable semantic version, got {current}")
    parts = list(map(int, current.split(".")))
    index = {"major": 0, "minor": 1, "patch": 2}[bump]
    parts[index] += 1
    parts[index + 1 :] = [0] * (2 - index)
    target = ".".join(map(str, parts))
    # All file mutations happen after branch creation; a failure leaves recoverable work.
    run(root, "git", "switch", "-c", f"release/v{target}")
    run(root, "uv", "version", "--bump", bump)
    # Date the entry in UTC so it matches the tag and GitHub release, whatever the local clock says.
    today = datetime.now(UTC).date().isoformat()
    run(root, "uv", "run", "towncrier", "build", "--yes", "--version", target, "--date", today)
    run(root, "uv", "lock")
    run(root, "just", "docs")
    print(f"Prepared release/v{target}. Review version, changelog, and release-status wording.")
    for error in check(root):
        print(error)
    print("Update the listed notices, then run just release-pr to validate and open a draft PR.")


def open_pr(root: Path) -> None:
    target = version(root)
    branch = f"release/v{target}"
    if run(root, "git", "branch", "--show-current") != branch:
        raise ValueError(f"run from {branch}")
    if run(root, "git", "ls-files", "--others", "--exclude-standard"):
        raise ValueError("review and commit untracked files before opening the release PR")
    if fragment_paths(root):
        raise ValueError("build and consume pending fragments before opening the release PR")
    _, sections = parse((root / "CHANGELOG.md").read_text())
    if (
        len(sections) < 2
        or sections[0][0] != "Unreleased"
        or re.search(r"^- ", sections[0][2], re.MULTILINE)
        or sections[1][0] != target
        or not re.search(r"^- ", sections[1][2], re.MULTILINE)
        or sections[1][1] is None
    ):
        raise ValueError(
            f"roll the changelog into a dated [{target}] section before opening the PR"
        )
    # Stream the full gate so failures stay visible; nothing is pushed before it succeeds.
    subprocess.run(["just", "check"], cwd=root, check=True)
    run(root, "git", "add", "--update")
    if run(root, "git", "diff", "--cached", "--name-only"):
        run(root, "git", "commit", "-m", f"chore: release v{target}")
    run(root, "git", "push", "-u", "origin", branch)
    with tempfile.TemporaryDirectory(prefix="usdata-release-") as directory:
        body = Path(directory) / "body.md"
        body.write_text(
            f"Prepare v{target} with the maintained changelog and release documentation.\n\n"
            "Validation: `just check` passed before opening this draft.\n\n"
            "Review the release diff and hosted checks before marking ready and enabling "
            "squash merge. Merging publishes the exact successful main CI artifacts.\n"
        )
        print(
            run(
                root,
                "gh",
                "pr",
                "create",
                "--draft",
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                f"chore: release v{target}",
                "--body-file",
                str(body),
            )
        )
    print("Obtain independent review, mark the PR ready, and wait for CI before enabling merge.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "pr"])
    parser.add_argument("bump", nargs="?", choices=["patch", "minor", "major"], default="minor")
    args = parser.parse_args()
    try:
        prepare(ROOT, args.bump) if args.command == "prepare" else open_pr(ROOT)
    except (ValueError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        parser.exit(
            1, f"Release stopped: {detail or exc}\nInspect git status; prepared work is retained.\n"
        )

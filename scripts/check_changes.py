"""Validate release-note fragments without requiring a feature-branch comparison."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fragment_paths(root: Path) -> list[Path]:
    directory = root / "changes"
    return (
        sorted(path for path in directory.iterdir() if path.name != "README.md")
        if directory.exists()
        else []
    )


def check(root: Path) -> list[str]:
    config = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["towncrier"]
    kinds = "|".join(re.escape(kind["directory"]) for kind in config["type"])
    pattern = re.compile(rf"(?:\d+|\+[a-z0-9-]+)\.(?:{kinds})\.md")
    errors = []
    for path in fragment_paths(root):
        if not path.is_file() or path.is_symlink() or not pattern.fullmatch(path.name):
            errors.append(f"{path.name}: expected NUMBER.type.md or +unique-slug.type.md")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(
                f"{path.name}: write a user-facing note or an internal-change explanation"
            )
    return errors


def preview(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "towncrier", "build", "--draft", "--version", "Unreleased"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    # Towncrier supplies a version heading; the preview owns its own timeless heading.
    _, separator, body = result.stdout.partition("\n")
    if not separator or not result.stdout.startswith("## [Unreleased]"):
        raise ValueError("unexpected Towncrier preview format")
    return body.strip() or "No public changes pending."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    errors = check(ROOT)
    if errors:
        sys.exit("\n".join(errors))
    print(
        "# Upcoming changes\n\n" + preview(ROOT)
        if args.preview
        else "release-note fragments are valid"
    )

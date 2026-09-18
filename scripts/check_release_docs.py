"""Reject known stale release-status wording in maintained docs.

Checks versioned source-only notices and roadmap Now headings against the
package version, and refuses a source-only notice that names no version, since
nothing can then tell when it goes stale. Historical ADRs and the changelog are
intentionally excluded. This is a guard for known release transitions, not a
general prose validator.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = r"(?P<version>\d+\.\d+(?:\.\d+)?)"
PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"available\s+from\s+source\s+for\s+(?:the\s+unreleased\s+)?v{VERSION}",
        rf"until\s+v{VERSION}\s+is\s+published",
        rf"v{VERSION}\s*/\s*source",
        rf"v{VERSION}\s+features\s+are\s+implemented\s+in\s+source\s+and\s+await\s+release",
        rf"\*\*Now\s+\(v{VERSION}\)\*\*",
    )
]

UNVERSIONED = re.compile(
    r"available\s+from\s+source(?!\s+for\s+(?:the\s+unreleased\s+)?v\d)", re.IGNORECASE
)
"""A source-only notice that does not go on to name the version it waits for."""


def version_key(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in value.split(".")]
    if len(parts) not in (2, 3):
        raise ValueError(f"expected a minor or patch version, got {value!r}")
    return parts[0], parts[1], parts[2] if len(parts) == 3 else 0


def stale_notices(text: str, version: str) -> list[tuple[int, str]]:
    """Find source-only notices whose target version is already declared shipped."""
    current = version_key(version)
    return sorted(
        (text.count("\n", 0, match.start()) + 1, " ".join(match[0].split()))
        for pattern in PATTERNS
        for match in pattern.finditer(text)
        if version_key(match["version"]) <= current
    )


def unversioned_notices(text: str) -> list[tuple[int, str]]:
    """Find source-only notices that name no version, which no release could ever flag.

    Three of these outlived their releases unnoticed, two by eight versions,
    because ``stale_notices`` reads the version a notice names and these named
    none. Writing "available from source for v0.21" is what lets the release
    that ships it say so.
    """
    return [
        (text.count("\n", 0, match.start()) + 1, " ".join(match[0].split()))
        for match in UNVERSIONED.finditer(text)
    ]


def _problems(text: str, version: str) -> list[tuple[int, str]]:
    """Every notice in ``text`` a release has to deal with, as (line, message), in line order."""
    stale = [
        (line, f"stale for {version}: {notice}") for line, notice in stale_notices(text, version)
    ]
    unversioned = [
        (line, f"names no version, so no release can flag it: {notice}")
        for line, notice in unversioned_notices(text)
    ]
    return sorted(stale + unversioned)


def check(root: Path) -> list[str]:
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    paths = [root / "README.md"]
    paths.extend(
        path
        for path in (root / "docs").rglob("*.md")
        if not {"adr", "examples", "generated"}.intersection(path.relative_to(root / "docs").parts)
    )
    paths.extend((root / "examples").rglob("*.md"))
    paths.extend(path for path in [root / "mkdocs.yml"] if path.exists())
    errors = [
        f"{path.relative_to(root)}:{line}: {problem}"
        for path in sorted(paths)
        for line, problem in _problems(path.read_text(encoding="utf-8"), version)
    ]
    for path in sorted((root / "examples").rglob("*.ipynb")):
        if ".ipynb_checkpoints" in path.parts:
            continue
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook["cells"], 1):
            if cell["cell_type"] != "markdown":
                continue
            source = cell["source"]
            text = "".join(source) if isinstance(source, list) else source
            errors.extend(
                f"{path.relative_to(root)}:cell {index}:{line}: {problem}"
                for line, problem in _problems(text, version)
            )
    return errors


if __name__ == "__main__":
    errors = check(ROOT)
    if errors:
        sys.exit("\n".join(errors) + "\nUpdate release-status notes before merging the release PR.")
    print("release-status notices are current")

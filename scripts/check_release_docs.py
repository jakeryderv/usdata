"""Reject known stale release-status wording in maintained docs.

Checks versioned source-only notices and roadmap Now headings against the
package version. Historical ADRs and the changelog are intentionally excluded.
This is a guard for known release transitions, not a general prose validator.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = r"(?P<version>\d+\.\d+(?:\.\d+)?)"
PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"available\s+from\s+source\s+for\s+v{VERSION}",
        rf"until\s+v{VERSION}\s+is\s+published",
        rf"v{VERSION}\s*/\s*source",
        rf"v{VERSION}\s+features\s+are\s+implemented\s+in\s+source\s+and\s+await\s+release",
        rf"\*\*Now\s+\(v{VERSION}\)\*\*",
    )
]


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


def check(root: Path) -> list[str]:
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    paths = [root / "README.md"]
    paths.extend(path for path in (root / "docs").rglob("*.md") if "adr" not in path.parts)
    paths.extend((root / "examples").rglob("*.md"))
    return [
        f"{path.relative_to(root)}:{line}: stale for {version}: {notice}"
        for path in sorted(paths)
        for line, notice in stale_notices(path.read_text(encoding="utf-8"), version)
    ]


if __name__ == "__main__":
    errors = check(ROOT)
    if errors:
        sys.exit("\n".join(errors) + "\nUpdate release-status notes before merging the release PR.")
    print("release-status notices are current")

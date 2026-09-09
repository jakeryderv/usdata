"""Read version sections from the Towncrier-maintained changelog for publishing."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
REPO = "https://github.com/jakeryderv/usdata"
HEADING = re.compile(
    r"^## \[(?P<name>[^\]]+)\](?:\([^\n)]+\))?(?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
LINK = re.compile(r"^\[[^\]]+\]: \S+$")


def parse(text: str) -> tuple[str, list[tuple[str, str | None, str]]]:
    """Return (preamble, [(name, date, body)]) with link-reference lines dropped."""
    preamble: list[str] = []
    sections: list[tuple[str, str | None, list[str]]] = []
    for line in text.splitlines():
        if LINK.match(line):
            continue
        m = HEADING.match(line)
        if m:
            sections.append((m["name"], m["date"], []))
        elif sections:
            sections[-1][2].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble).rstrip() + "\n", [
        (n, d, "\n".join(b).strip("\n")) for n, d, b in sections
    ]


def notes(version: str) -> None:
    _, sections = parse(PATH.read_text())
    for name, _, body in sections:
        if name == version:
            print(body)
            return
    sys.exit(f"no changelog section for {version}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["notes", version]:
            notes(version)
        case _:
            sys.exit(__doc__)

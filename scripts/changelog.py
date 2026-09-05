"""Maintain CHANGELOG.md in Keep a Changelog format.

roll VERSION    move the Unreleased section under a dated VERSION heading
notes VERSION   print the body of VERSION's section (used for release notes)
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
REPO = "https://github.com/jakeryderv/usdata"
HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$")
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


def render(preamble: str, sections: list[tuple[str, str | None, str]]) -> str:
    out = [preamble]
    for name, date, body in sections:
        heading = f"## [{name}]" + (f" - {date}" if date else "")
        out.append(heading + "\n" + (f"\n{body}\n" if body else ""))
    versions = [n for n, _, _ in sections if n != "Unreleased"]
    links = [f"[Unreleased]: {REPO}/compare/v{versions[0]}...HEAD"] if versions else []
    for cur, prev in zip(versions, [*versions[1:], None], strict=True):
        links.append(
            f"[{cur}]: {REPO}/compare/v{prev}...v{cur}"
            if prev
            else f"[{cur}]: {REPO}/releases/tag/v{cur}"
        )
    return "\n".join(out) + "\n" + "\n".join(links) + "\n"


def roll(version: str) -> None:
    preamble, sections = parse(PATH.read_text())
    if not sections or sections[0][0] != "Unreleased":
        sys.exit("CHANGELOG.md must start with an [Unreleased] section")
    body = sections[0][2]
    if not re.search(r"^- ", body, re.M):
        sys.exit("Unreleased section is empty; add changelog entries before releasing")
    if any(n == version for n, _, _ in sections):
        sys.exit(f"version {version} already has a changelog section")
    today = dt.datetime.now(dt.UTC).date().isoformat()
    new = [("Unreleased", None, ""), (version, today, body), *sections[1:]]
    PATH.write_text(render(preamble, new))
    print(f"rolled Unreleased into [{version}] - {today}")


def notes(version: str) -> None:
    _, sections = parse(PATH.read_text())
    for name, _, body in sections:
        if name == version:
            print(body)
            return
    sys.exit(f"no changelog section for {version}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["roll", version]:
            roll(version)
        case ["notes", version]:
            notes(version)
        case _:
            sys.exit(__doc__)

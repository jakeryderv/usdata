"""Print the lowest version pyproject.toml allows for a dependency, for CI floor checks.

The lockfile always resolves the newest compatible release, so a `>=` floor is
never executed unless a job installs it deliberately. CI reads the number from
here instead of repeating it in the workflow, which also keeps every declaration
of the same distribution in step.
"""

import re
import sys
import tomllib
from pathlib import Path
from typing import Any

FLOOR = re.compile(r">=\s*([0-9][0-9a-zA-Z.*+!-]*)")


def requirements(pyproject: dict[str, Any]) -> list[str]:
    project = pyproject.get("project", {})
    groups: list[Any] = [project.get("dependencies", [])]
    groups += project.get("optional-dependencies", {}).values()
    groups += pyproject.get("dependency-groups", {}).values()
    return [r for group in groups for r in group if isinstance(r, str)]


def lowest_version(name: str, pyproject: dict[str, Any]) -> str:
    named = re.compile(rf"{re.escape(name)}(?![\w.-])")
    floors = {
        match[1]
        for req in requirements(pyproject)
        if named.match(req) and (match := FLOOR.search(req))
    }
    if len(floors) != 1:
        raise SystemExit(
            f"expected exactly one '>=' floor for {name} in pyproject.toml, found {sorted(floors)}"
        )
    return floors.pop()


if __name__ == "__main__":
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    print(lowest_version(sys.argv[1], data))

"""Generate documentation references before a normal MkDocs build."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import render_registry
from check_changes import preview

from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    render_registry.sync(render_registry.render_all(Registry.bundled()), check=False)
    # Remove only the former, explicitly disposable generated examples tree.
    # Examples are now published exclusively by the main website build.
    old_examples = ROOT / "docs/examples"
    if old_examples.exists():
        shutil.rmtree(old_examples)
    cli = subprocess.run(
        [sys.executable, "-m", "typer", "usdata.cli.app", "utils", "docs", "--name", "usdata"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (ROOT / "docs/generated/cli.md").write_text("# CLI reference\n\n" + cli)
    (ROOT / "docs/generated/changes.md").write_text(
        "# Upcoming changes\n\nThese changes are not yet released.\n\n" + preview(ROOT)
    )


if __name__ == "__main__":
    main()

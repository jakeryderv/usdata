"""Generate references and saved notebook previews before a normal MkDocs build."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import render_registry
from check_changes import preview

from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def generate_examples(root: Path = ROOT) -> None:
    """Export saved outputs without executing notebooks or rewriting their links."""
    import nbformat
    from nbconvert import MarkdownExporter

    output = root / "docs/examples"
    # This entire ignored directory is generated; source examples stay untouched.
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    examples = root / "examples"
    for source in [examples / "README.md", *sorted(examples.glob("*/README.md"))]:
        target = output / source.relative_to(examples)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'--8<-- "{source.relative_to(root).as_posix()}"\n')
    for source in sorted(examples.glob("*/dataset.yaml")):
        target = output / source.relative_to(examples)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    exporter = MarkdownExporter()
    for source in sorted(examples.glob("*/example.ipynb")):
        target = output / source.relative_to(examples)
        target.parent.mkdir(parents=True, exist_ok=True)
        body, resources = exporter.from_notebook_node(
            nbformat.read(source, as_version=4),
            resources={"output_files_dir": "example_files"},
        )
        target.with_suffix(".md").write_text(
            "> Saved notebook output; cells are not executed during documentation builds. "
            "[Download the notebook](example.ipynb).\n\n" + body
        )
        shutil.copyfile(source, target)
        for name, data in resources.get("outputs", {}).items():
            image = target.parent / name
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(data)


def main() -> None:
    render_registry.sync(render_registry.render_all(Registry.bundled()), check=False)
    generate_examples()
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

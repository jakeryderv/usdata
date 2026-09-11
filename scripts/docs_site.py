"""Assemble canonical docs and saved notebooks for MkDocs, without live execution.

The staging tree keeps repository paths except for the home and project pages.
Relative links are adjusted for those pages and rendered notebook previews.
"""

from __future__ import annotations

import argparse
import importlib
import posixpath
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import render_registry
import yaml
from check_changes import preview

from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".build/docs"
# Only local inline Markdown notebook links; remote links and code remain intact.
NOTEBOOK_LINK = re.compile(r"(\]\()((?![a-zA-Z][\w+.-]*:)[^\s()]+)\.ipynb([#?][^\s()]*)?(\))")


def notebook_links(text: str) -> str:
    return NOTEBOOK_LINK.sub(r"\1\2.md\3\4", text)


PAGE_PATHS = {
    Path("docs/index.md"): Path("index.md"),
    Path("README.md"): Path("project.md"),
}
LOCAL_LINK = re.compile(r"(\]\()([^\s()]+)(\))")


def site_path(path: Path) -> Path:
    return PAGE_PATHS.get(path, path)


def page_links(text: str, source: Path, destination_page: Path | None = None) -> str:
    def replace(match: re.Match[str]) -> str:
        url = urlsplit(match[2])
        if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
            return match[0]
        target = Path(posixpath.normpath((source.parent / url.path).as_posix()))
        destination = site_path(target)
        relative = posixpath.relpath(
            destination.as_posix(), (destination_page or site_path(source)).parent.as_posix()
        )
        return match[1] + urlunsplit(("", "", relative, url.query, url.fragment)) + match[3]

    return LOCAL_LINK.sub(replace, notebook_links(text))


def source_paths() -> list[Path]:
    paths = [
        ROOT / name
        for name in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md", "SECURITY.md", "LICENSE")
    ]
    paths.append(ROOT / "changes/README.md")
    for directory in ("docs", "examples"):
        paths.extend(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and path.suffix in {".md", ".ipynb", ".yaml", ".png", ".svg", ".css"}
            and ".ipynb_checkpoints" not in path.parts
            and not path.is_relative_to(ROOT / "docs/theme")
            and not path.is_relative_to(ROOT / "docs/hosting")
        )
    return sorted(paths)


def prepare() -> None:
    import nbformat
    from nbconvert import MarkdownExporter

    registry = Registry.bundled()
    renderer = importlib.reload(render_registry)
    entries = renderer.catalog_entries(registry)
    PAGE_PATHS.clear()
    PAGE_PATHS.update(
        {
            Path("docs/index.md"): Path("index.md"),
            Path("README.md"): Path("project.md"),
        }
    )
    PAGE_PATHS.update(
        {
            Path(entry.guide): renderer.dataset_path(registry.get(key))
            for key, entry in entries.items()
        }
    )
    guides = {Path(entry.guide) for entry in entries.values()}
    generated = renderer.render_all(registry)
    outputs: dict[Path, bytes] = {}
    exporter = MarkdownExporter()
    for path in source_paths():
        relative = path.relative_to(ROOT)
        if relative in guides or path.is_relative_to(renderer.CATALOG_DIR):
            continue
        if path.suffix == ".ipynb":
            body, resources = exporter.from_notebook_node(
                nbformat.read(path, as_version=4),
                resources={"unique_key": path.stem, "output_files_dir": f"{path.stem}_files"},
            )
            body = page_links(body, relative)
            body = (
                f"> Saved notebook output; this documentation build does not execute cells. "
                f"[Download the notebook]({path.name}).\n\n" + body
            )
            outputs[relative.with_suffix(".md")] = body.encode()
            for name, data in resources.get("outputs", {}).items():
                outputs[relative.parent / name] = data
            outputs[relative] = path.read_bytes()
        elif path.suffix == ".md":
            outputs[site_path(relative)] = page_links(path.read_text(), relative).encode()
        else:
            outputs[relative] = path.read_bytes()
    for path, content in generated.items():
        relative = path.relative_to(ROOT)
        content = content.replace(
            renderer.GENERATED_NOTE, "<!-- Registry facts; edit the source catalog. -->"
        )
        outputs[site_path(relative)] = page_links(content, relative).encode()
    for key, entry in entries.items():
        ds = registry.get(key)
        destination = renderer.dataset_path(ds)
        guide = Path(entry.guide)
        text = (ROOT / guide).read_text()
        if not text.startswith("# "):
            raise ValueError(f"{guide}: usage guide needs a level-one title")
        body = text.split("\n", 1)[1].strip()
        # Each source resolves links in its own directory before insertion.
        body = page_links(body, guide, destination)
        marker = page_links(renderer.usage_link(ds, entry), destination)
        outputs[destination] = outputs[destination].decode().replace(marker, body).encode()
    for path in (ROOT / "docs/theme/assets").rglob("*"):
        if path.is_file():
            outputs[Path("assets") / path.relative_to(ROOT / "docs/theme/assets")] = (
                path.read_bytes()
            )
    outputs[Path("_headers")] = (ROOT / "docs/hosting/_headers").read_bytes()
    write_config(registry, entries)
    pending = preview(ROOT)
    outputs[Path("docs/generated/changes.md")] = (
        "# Upcoming changes\n\nGenerated from release-note fragments. "
        "These changes are not yet released.\n\n"
        + pending
        + "\n\n[Published releases](../../CHANGELOG.md).\n"
    ).encode()
    cli = subprocess.run(
        [sys.executable, "-m", "typer", "usdata.cli.app", "utils", "docs", "--name", "usdata"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    outputs[Path("docs/generated/cli.md")] = (
        "<!-- Generated by scripts/docs_site.py from the Typer app; do not edit. -->\n"
        "# CLI reference\n\nGenerated from the current CLI. "
        "See the [fetch guide](../guides/fetch-and-analyze.md) for workflows.\n\n" + cli
    ).encode()
    for relative, data in outputs.items():
        target = STAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
    for path in STAGE.rglob("*"):
        if path.is_file() and path.relative_to(STAGE) not in outputs:
            path.unlink()
    print(f"Prepared {len(outputs)} documentation files from canonical sources", flush=True)


def dataset_navigation(registry: Registry, entries: dict) -> list[dict]:
    items = [{"Find a dataset": "docs/generated/catalog/index.md"}]
    for info, datasets in render_registry.by_provider(registry):
        pages = [{"Overview": f"docs/generated/catalog/{info.id}.md"}]
        pages += [
            {entries[ds.id].summary: render_registry.dataset_path(ds).as_posix()}
            for ds in datasets
            if ds.status.value == "available"
        ]
        pages += [{"Access notes": f"docs/providers/{info.id}.md"}]
        items.append({info.name: pages})
    items.append({"Versions and targets": "docs/generated/catalog/versions.md"})
    return items


def write_config(registry: Registry, entries: dict) -> None:
    text = (ROOT / "mkdocs.yml").read_text()
    marker = "- Datasets: []"
    if text.count(marker) != 1:
        raise ValueError("mkdocs.yml must have exactly one empty Datasets section")
    navigation = yaml.safe_dump(
        [{"Datasets": dataset_navigation(registry, entries)}], sort_keys=False
    ).rstrip()
    path = ROOT / ".mkdocs.generated.yml"
    content = text.replace(marker, navigation)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)


def fingerprint() -> list[tuple[str, int]]:
    paths = source_paths() + list((ROOT / "src").rglob("*.py"))
    paths += list((ROOT / "changes").glob("*.md"))
    paths += [
        ROOT / "src/usdata/data/registry.yaml",
        ROOT / "pyproject.toml",
        ROOT / "mkdocs.yml",
        ROOT / "docs/hosting/_headers",
    ]
    paths += [
        path
        for directory in (ROOT / "docs/theme/assets",)
        for path in directory.rglob("*")
        if path.is_file()
    ]
    paths += list((ROOT / "scripts").glob("*.py")) + list((ROOT / "scripts/templates").glob("*"))
    return [(str(path), path.stat().st_mtime_ns) for path in sorted(paths)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "build", "serve"])
    args = parser.parse_args()
    prepare()
    if args.command == "prepare":
        return
    if args.command == "build":
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "-f",
                ".mkdocs.generated.yml",
                "--clean",
                "--strict",
            ],
            cwd=ROOT,
            check=True,
        )
        return
    before = fingerprint()
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "serve",
            "-f",
            ".mkdocs.generated.yml",
            "--dev-addr",
            "127.0.0.1:8000",
        ],
        cwd=ROOT,
    )
    try:
        while server.poll() is None:
            time.sleep(0.5)
            after = fingerprint()
            if after != before:
                prepare()
                before = after
    except KeyboardInterrupt:
        pass
    finally:
        server.terminate()
        server.wait()
    if server.returncode not in (0, -2, -15):
        sys.exit(server.returncode)


if __name__ == "__main__":
    main()

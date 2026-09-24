"""Execute selected live examples, retaining diagnostics and refreshing only on success."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from collections.abc import Callable, Collection, Mapping
from pathlib import Path

from check_notebooks import ROOT, check_notebook, notebook_paths, pinned_manifests

CACHE_ENVIRONMENT_VARIABLE = "USDATA_NOTEBOOK_CACHE"


def resolve_cache_dir(
    option: str | None = None, environ: Mapping[str, str] | None = None
) -> Path | None:
    """The warm cache directory to reuse across runs, or ``None`` for a fresh one.

    ``option`` is the ``--cache`` value and wins over the
    ``USDATA_NOTEBOOK_CACHE`` environment variable; an empty or unset value from
    either source selects the default of a fresh directory per run. The returned
    path is absolute but is not created here.
    """
    environment = os.environ if environ is None else environ
    name = option or environment.get(CACHE_ENVIRONMENT_VARIABLE, "")
    return Path(name).expanduser().resolve() if name.strip() else None


def execute_notebook(source: Path, output: Path, kernel_dir: Path, cache_dir: Path) -> None:
    import nbformat
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager
    from nbclient import NotebookClient

    notebook = nbformat.read(source, as_version=4)
    manager = KernelManager(
        kernel_name="python3",
        kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_dir.parent)]),
    )
    try:
        NotebookClient(
            notebook,
            km=manager,
            timeout=300,
            resources={"metadata": {"path": str(source.parent)}},
            record_timing=False,
        ).execute(
            cleanup_kc=True,
            env={**os.environ, "USDATA_CACHE_DIR": str(cache_dir)},
        )
    finally:
        # Preserve partial outputs and error cells even when execution raises.
        notebook.metadata.pop("widgets", None)
        for cell in notebook.cells:
            cell.metadata.pop("execution", None)
        nbformat.write(notebook, output)


def run_notebooks(
    paths: list[Path],
    output_dir: Path,
    *,
    write: bool = False,
    cache_dir: Path | None = None,
    pinned: Collection[Path] | None = None,
    execute: Callable[[Path, Path, Path, Path], None] = execute_notebook,
) -> list[str]:
    """Execute ``paths``, writing diagnostics to ``output_dir`` and returning failures.

    ``cache_dir``, when given, is reused as ``USDATA_CACHE_DIR`` by every
    notebook so repeated runs do not re-download; the default gives each
    notebook a fresh cache under a temporary working directory. ``pinned``
    names the manifests whose committed lockfile travels with them, so those
    notebooks restore their pins instead of resolving again; it defaults to the
    catalog's pinned examples.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pinned_dirs = {
        manifest.parent.resolve() for manifest in (pinned_manifests() if pinned is None else pinned)
    }
    failures: list[str] = []
    results = []
    executed_paths = []
    with tempfile.TemporaryDirectory(prefix="usdata-notebooks-") as temp:
        temporary = Path(temp)
        kernel_dir = temporary / "kernels" / "python3"
        kernel_dir.mkdir(parents=True)
        (kernel_dir / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": "Python 3 (usdata examples)",
                    "language": "python",
                }
            ),
            encoding="utf-8",
        )
        for index, path in enumerate(paths):
            print(f"Executing {path}", flush=True)
            if cache_dir is not None:
                print(f"Reusing warm cache {cache_dir} for {path}", flush=True)
            started = time.monotonic()
            working_dir = temporary / f"example-{index}"
            working_dir.mkdir()
            executed = output_dir / f"{index}-{path.stem}.ipynb"
            diagnostic = output_dir / f"{index}-error.txt"
            executed.unlink(missing_ok=True)
            diagnostic.unlink(missing_ok=True)
            status = "passed"
            try:
                shutil.copy2(path, working_dir / path.name)
                manifest = path.parent / "dataset.yaml"
                if manifest.exists():
                    shutil.copy2(manifest, working_dir / manifest.name)
                lockfile = manifest.with_suffix(".lock.json")
                if path.parent.resolve() in pinned_dirs and lockfile.exists():
                    shutil.copy2(lockfile, working_dir / lockfile.name)
                cache = cache_dir if cache_dir is not None else working_dir / "cache"
                cache.mkdir(parents=True, exist_ok=True)
                execute(working_dir / path.name, executed, kernel_dir, cache)
                errors = check_notebook(executed)
                if errors:
                    raise ValueError("\n".join(errors))
                executed_paths.append((path, executed))
            except Exception as exc:
                status = "failed"
                failures.append(f"{path}: {exc}")
                diagnostic.write_text(traceback.format_exc(), encoding="utf-8")
            results.append(
                {
                    "path": str(path),
                    "status": status,
                    "seconds": round(time.monotonic() - started, 3),
                    "output": executed.name if executed.exists() else None,
                    "error": diagnostic.name if status == "failed" else None,
                }
            )
        # Never refresh a subset after another selected example fails.
        if write and not failures:
            for original, executed in executed_paths:
                original.write_bytes(executed.read_bytes())
    (output_dir / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return failures


def resolve_notebooks(names: list[str], paths: list[Path], *, root: Path = ROOT) -> list[Path]:
    """The subset of ``paths`` that ``names`` selects, by example folder or by path.

    A folder name, such as ``noaa-goes-glm`` or ``storm-surge``, selects the
    notebook in it; a path is repository-relative, such as
    ``examples/datasets/noaa-goes-glm/noaa-goes-glm.ipynb``. Results keep the order of
    ``paths`` and repeats collapse. A name that selects nothing raises
    ``ValueError`` quoting exactly what was typed.
    """
    by_path = {path.resolve(): path for path in paths}
    by_slug: dict[str, list[Path]] = {}
    for path in paths:
        by_slug.setdefault(path.parent.name, []).append(path)
    selected: set[Path] = set()
    unknown: list[str] = []
    for name in names:
        matched = by_slug.get(name.strip("/"))
        if matched is None:
            one = by_path.get((root / name).resolve())
            matched = [one] if one is not None else None
        if matched is None:
            unknown.append(name)
            continue
        selected.update(matched)
    if unknown:
        raise ValueError(
            f"unknown example notebook(s): {', '.join(unknown)}; "
            "name an example folder (noaa-goes-glm) or a repository-relative path "
            "(examples/datasets/noaa-goes-glm/noaa-goes-glm.ipynb)"
        )
    return [path for path in paths if path in selected]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="refresh selected notebooks only if all pass"
    )
    parser.add_argument(
        "--notebook",
        action="append",
        default=[],
        help="example folder (noaa-goes-glm) or repository-relative path; repeatable",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/notebooks")
    parser.add_argument(
        "--cache",
        default=None,
        help=(
            "reuse this directory as USDATA_CACHE_DIR for every notebook instead of a fresh "
            f"one per run; also settable as {CACHE_ENVIRONMENT_VARIABLE}"
        ),
    )
    args = parser.parse_args()
    paths = notebook_paths()
    if args.notebook:
        try:
            paths = resolve_notebooks(args.notebook, paths)
        except ValueError as exc:
            parser.error(str(exc))
    if not paths:
        parser.error("No example notebooks found")
    failures = run_notebooks(
        paths,
        args.output_dir.resolve(),
        write=args.write,
        cache_dir=resolve_cache_dir(args.cache),
    )
    if failures:
        sys.exit("\n".join(failures))
    action = "refreshed" if args.write else "executed (committed outputs unchanged)"
    print(f"{len(paths)} notebooks {action}; diagnostics: {args.output_dir}")


if __name__ == "__main__":
    main()

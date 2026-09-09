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
from collections.abc import Callable
from pathlib import Path

from check_notebooks import ROOT, check_notebook, notebook_paths


def execute_notebook(source: Path, output: Path, kernel_dir: Path) -> None:
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
            env={**os.environ, "USDATA_CACHE_DIR": str(source.parent / "cache")},
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
    execute: Callable[[Path, Path, Path], None] = execute_notebook,
) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
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
                execute(working_dir / path.name, executed, kernel_dir)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="refresh selected notebooks only if all pass"
    )
    parser.add_argument(
        "--notebook",
        action="append",
        default=[],
        help="repository-relative example path; repeatable",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/notebooks")
    args = parser.parse_args()
    paths = notebook_paths()
    if args.notebook:
        selected = {(ROOT / name).resolve() for name in args.notebook}
        unknown = selected - {path.resolve() for path in paths}
        if unknown:
            parser.error(f"unknown example notebooks: {', '.join(map(str, sorted(unknown)))}")
        paths = [path for path in paths if path.resolve() in selected]
    if not paths:
        parser.error("No example notebooks found")
    failures = run_notebooks(paths, args.output_dir.resolve(), write=args.write)
    if failures:
        sys.exit("\n".join(failures))
    action = "refreshed" if args.write else "executed (committed outputs unchanged)"
    print(f"{len(paths)} notebooks {action}; diagnostics: {args.output_dir}")


if __name__ == "__main__":
    main()

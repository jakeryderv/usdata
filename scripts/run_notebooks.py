"""Execute live examples in fresh kernels; optionally refresh saved outputs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from check_notebooks import check_notebook, notebook_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="refresh notebooks only after every example succeeds"
    )
    args = parser.parse_args()

    import nbformat
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager
    from nbclient import NotebookClient

    paths = notebook_paths()
    if not paths:
        sys.exit("No example notebooks found")
    # Use this uv environment's interpreter without installing a global kernel.
    # Default runs keep executed copies in a temporary directory, never in Git.
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
        executed_paths = []
        for index, path in enumerate(paths):
            print(f"Executing {path.relative_to(path.parents[2])}", flush=True)
            working_dir = temporary / path.parent.name
            working_dir.mkdir()
            shutil.copy2(path, working_dir / path.name)
            manifest = path.parent / "dataset.yaml"
            if manifest.exists():
                shutil.copy2(manifest, working_dir / manifest.name)
            notebook = nbformat.read(path, as_version=4)
            manager = KernelManager(
                kernel_name="python3",
                kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_dir.parent)]),
            )
            NotebookClient(
                notebook,
                km=manager,
                timeout=300,
                resources={"metadata": {"path": str(working_dir)}},
                record_timing=False,
            ).execute(
                cleanup_kc=True,
                env={**os.environ, "USDATA_CACHE_DIR": str(temporary / "cache")},
            )
            notebook.metadata.pop("widgets", None)
            for cell in notebook.cells:
                cell.metadata.pop("execution", None)
            executed = temporary / f"{index}.ipynb"
            nbformat.write(notebook, executed)
            errors = check_notebook(executed)
            if errors:
                sys.exit("\n".join(errors))
            executed_paths.append((path, executed))
        if args.write:
            for original, executed in executed_paths:
                original.write_bytes(executed.read_bytes())
    action = "refreshed" if args.write else "executed (committed outputs unchanged)"
    print(f"{len(paths)} notebooks {action}")


if __name__ == "__main__":
    main()

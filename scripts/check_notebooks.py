"""Check that example notebooks contain small, successful saved executions.

Uses only the standard library so ordinary CI can check the committed examples
without installing Jupyter or contacting their live data services.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_OUTPUT_BYTES = 1_000_000


def notebook_paths(root: Path = ROOT) -> list[Path]:
    return sorted(
        path
        for path in (root / "examples").rglob("*.ipynb")
        if ".ipynb_checkpoints" not in path.parts
    )


def is_text(value: object) -> bool:
    return isinstance(value, str) or (
        isinstance(value, list) and all(isinstance(line, str) for line in value)
    )


def check_notebook(path: Path) -> list[str]:
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"{path}: cannot read notebook: {exc}"]
    if (
        not isinstance(notebook, dict)
        or notebook.get("nbformat") != 4
        or not isinstance(notebook.get("cells"), list)
        or not isinstance(notebook.get("metadata"), dict)
    ):
        return [f"{path}: expected a v4 notebook with cells and metadata"]

    errors = []
    expected_count = 1
    output_size = 0
    has_output = False
    for index, cell in enumerate(notebook["cells"], start=1):
        prefix = f"{path}: cell {index}"
        if (
            not isinstance(cell, dict)
            or cell.get("cell_type") not in ("code", "markdown", "raw")
            or not is_text(cell.get("source"))
            or not isinstance(cell.get("metadata"), dict)
        ):
            errors.append(f"{prefix}: invalid cell structure")
            continue
        if cell["cell_type"] != "code":
            continue
        if cell.get("execution_count") != expected_count:
            errors.append(f"{prefix}: expected execution_count {expected_count}; run top-to-bottom")
        expected_count += 1
        outputs = cell.get("outputs")
        if not isinstance(outputs, list):
            errors.append(f"{prefix}: expected an outputs list")
            continue
        for output in outputs:
            output_size += len(json.dumps(output, ensure_ascii=False).encode("utf-8"))
            if not isinstance(output, dict):
                errors.append(f"{prefix}: invalid output")
                continue
            output_type = output.get("output_type")
            if output_type == "error":
                errors.append(f"{prefix}: saved error output")
            elif output_type == "stream":
                if not is_text(output.get("text")):
                    errors.append(f"{prefix}: stream output must contain text")
                elif output["text"]:
                    has_output = True
            elif output_type in ("display_data", "execute_result"):
                if not isinstance(output.get("data"), dict):
                    errors.append(f"{prefix}: display output must contain MIME data")
                elif output["data"]:
                    has_output = True
                if output_type == "execute_result" and output.get("execution_count") != cell.get(
                    "execution_count"
                ):
                    errors.append(f"{prefix}: result execution_count does not match its cell")
            else:
                errors.append(f"{prefix}: unknown output type {output_type!r}")
    if expected_count == 1 or not has_output:
        errors.append(f"{path}: expected executed code with saved output")
    if output_size > MAX_OUTPUT_BYTES:
        errors.append(
            f"{path}: saved outputs exceed 1 MB; shorten tables or reduce plot resolution"
        )
    return errors


def main() -> None:
    paths = notebook_paths()
    if not paths:
        sys.exit("No example notebooks found")
    errors = [error for path in paths for error in check_notebook(path)]
    if errors:
        sys.exit("\n".join(errors))
    print(f"{len(paths)} example notebooks have valid saved executions")


if __name__ == "__main__":
    main()

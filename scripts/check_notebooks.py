"""Check the committed example artifacts: saved notebook executions and pinned lockfiles.

Uses only the standard library so ordinary CI can check the committed examples
without installing Jupyter or contacting their live data services.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_OUTPUT_BYTES = 1_000_000


def catalog(root: Path = ROOT) -> dict[str, list]:
    """The example index, or an empty one where a checkout has none."""
    path = root / "examples/catalog.json"
    if not path.exists():
        return {"studies": [], "pinned": []}
    return json.loads(path.read_text(encoding="utf-8"))


def pinned_manifests(root: Path = ROOT) -> list[Path]:
    """Manifests of the examples whose lockfiles are committed, in catalog order.

    ``examples/catalog.json`` lists them under ``pinned`` as folders relative to
    ``examples/``, such as ``datasets/noaa-goes-abi``; ADR 0029 says which
    examples are pinned and why, and ADR 0041 where they live.
    """
    return [root / "examples" / str(folder) / "dataset.yaml" for folder in catalog(root)["pinned"]]


def check_lockfile(manifest: Path) -> list[str]:
    """Errors for a pinned manifest whose committed lockfile is missing or stale.

    The lockfile must parse, must record the sha256 of the manifest beside it,
    and must pin a checksum on every entry. Nothing here touches the network
    or the cache; it is the offline half of what the weekly restore proves.
    """
    lock = manifest.with_suffix(".lock.json")
    if not manifest.is_file():
        return [f"{manifest}: pinned example has no manifest"]
    if not lock.is_file():
        return [f"{lock}: pinned example has no committed lockfile; run usdata pull"]
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"{lock}: cannot read lockfile: {exc}"]
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        return [f"{lock}: expected a lockfile with an assets list"]
    errors = []
    digest = "sha256:" + hashlib.sha256(manifest.read_bytes()).hexdigest()
    if data.get("manifest_checksum") != digest:
        errors.append(f"{lock}: manifest changed since it was written; run usdata pull --force")
    if not data["assets"]:
        errors.append(f"{lock}: pins no assets")
    for index, entry in enumerate(data["assets"], start=1):
        asset = entry.get("asset") if isinstance(entry, dict) else None
        provenance = entry.get("provenance") if isinstance(entry, dict) else None
        if not isinstance(asset, dict) or not isinstance(provenance, dict):
            errors.append(f"{lock}: entry {index}: expected an asset and its provenance")
            continue
        checksum = provenance.get("checksum")
        if not isinstance(checksum, str) or not checksum.startswith("sha256:"):
            errors.append(f"{lock}: entry {index}: no sha256 pinned")
        elif asset.get("checksum") != checksum:
            errors.append(f"{lock}: entry {index}: asset and provenance checksums differ")
    return errors


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
    pinned = pinned_manifests()
    errors = [error for path in paths for error in check_notebook(path)]
    errors += [error for manifest in pinned for error in check_lockfile(manifest)]
    if errors:
        sys.exit("\n".join(errors))
    print(
        f"{len(paths)} example notebooks have valid saved executions; "
        f"{len(pinned)} committed lockfiles match their manifests"
    )


if __name__ == "__main__":
    main()

"""Restore committed example lockfiles into empty caches and report every asset that drifted.

Each pinned example is restored on its own: ``usdata.pull.restore`` downloads
exactly what the lockfile pins into a fresh cache directory, then ``verify``
re-hashes what landed. The lockfile is never rewritten; drift is reported, not
accepted. This is the weekly half of ADR 0029; the offline half is
``check_notebooks.check_lockfile``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from check_notebooks import ROOT, pinned_manifests

Restore = Callable[[Path, Path], list[dict[str, str]]]


def restore_pinned(manifest: Path, cache: Path) -> list[dict[str, str]]:
    """Restore ``manifest``'s lockfile into ``cache`` and return every drifted asset.

    A restore that raises ``UpstreamChanged`` is not an error here: its drift
    list is the result. Anything else propagates.
    """
    from usdata.pull import UpstreamChanged, restore, verify

    try:
        restore(manifest, root=cache)
    except UpstreamChanged as exc:
        return [{"asset_id": d.asset_id, "problem": d.problem} for d in exc.drift]
    return [{"asset_id": d.asset_id, "problem": d.problem} for d in verify(manifest, root=cache)]


def restore_examples(
    manifests: list[Path], output_dir: Path, *, restore: Restore = restore_pinned
) -> list[str]:
    """Restore each manifest's pins into its own empty cache; return the failures.

    Writes ``summary.json`` and, per example, a traceback file for anything that
    was not drift. Every example runs even after an earlier one fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for index, manifest in enumerate(manifests):
        print(f"Restoring {manifest}", flush=True)
        started = time.monotonic()
        lock = json.loads(manifest.with_suffix(".lock.json").read_text(encoding="utf-8"))
        diagnostic = output_dir / f"{index}-error.txt"
        diagnostic.unlink(missing_ok=True)
        drift: list[dict[str, str]] = []
        status = "restored"
        with tempfile.TemporaryDirectory(prefix="usdata-restore-") as temp:
            try:
                drift = restore(manifest, Path(temp) / "cache")
            except Exception as exc:
                status = "failed"
                failures.append(f"{manifest}: {exc}")
                diagnostic.write_text(traceback.format_exc(), encoding="utf-8")
        if drift:
            status = "drifted"
            changed = ", ".join(f"{d['asset_id']} ({d['problem']})" for d in drift)
            failures.append(f"{manifest}: {len(drift)} asset(s) drifted: {changed}")
        results.append(
            {
                "path": manifest.relative_to(ROOT).as_posix()
                if manifest.is_relative_to(ROOT)
                else str(manifest),
                "status": status,
                "assets": len(lock["assets"]),
                "bytes": sum(entry["provenance"]["size"] for entry in lock["assets"]),
                "seconds": round(time.monotonic() - started, 3),
                "drift": drift,
                "error": diagnostic.name if status == "failed" else None,
            }
        )
    (output_dir / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return failures


def resolve_manifests(names: list[str], manifests: list[Path], *, root: Path = ROOT) -> list[Path]:
    """The subset of pinned ``manifests`` that ``names`` selects, by slug or by path."""
    by_slug = {manifest.parent.name: manifest for manifest in manifests}
    by_path = {manifest.resolve(): manifest for manifest in manifests}
    selected: set[Path] = set()
    unknown: list[str] = []
    for name in names:
        manifest = by_slug.get(name.strip("/")) or by_path.get((root / name).resolve())
        if manifest is None:
            unknown.append(name)
        else:
            selected.add(manifest)
    if unknown:
        choices = ", ".join(sorted(by_slug))
        raise ValueError(f"not a pinned example: {', '.join(unknown)}; choose from: {choices}")
    return [manifest for manifest in manifests if manifest in selected]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        action="append",
        default=[],
        help="pinned example slug (glm-flashes) or repository-relative manifest path; repeatable",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/restore")
    args = parser.parse_args()
    manifests = pinned_manifests()
    if args.manifest:
        try:
            manifests = resolve_manifests(args.manifest, manifests)
        except ValueError as exc:
            parser.error(str(exc))
    if not manifests:
        parser.error("No pinned examples found")
    failures = restore_examples(manifests, args.output_dir.resolve())
    if failures:
        sys.exit("\n".join(failures))
    print(f"{len(manifests)} lockfiles restored and verified; reports: {args.output_dir}")


if __name__ == "__main__":
    main()

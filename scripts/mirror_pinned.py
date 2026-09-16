"""Upload the objects committed lockfiles pin to the R2 mirror, or prune what none pins.

The mirror is content-addressed (ADR 0030): an object lives at ``sha256/<hex>``
and nothing else, so uploading is idempotent and pruning is a set difference
between the bucket's keys and every checksum in every committed lockfile.
Only CI runs ``upload``, after a restore has passed; ``prune`` is a manual
workflow that prints its plan and deletes only when told to.

Bytes come from a cache the restore job filled (``--cache``), are re-hashed
before upload so a wrong file can never land under a right key, and are sent
with the AWS CLI against the bucket's S3 endpoint, as the storage check does.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

import httpx
from check_notebooks import ROOT, pinned_manifests
from restore_lockfiles import resolve_manifests

PUBLIC_URL = "https://data.usdata.dev"
BUCKET = "usdata"
PREFIX = "sha256/"
IMMUTABLE = "public, max-age=31536000, immutable"

Run = Callable[[list[str]], str]


def run(command: list[str]) -> str:
    """Run one AWS CLI command and return its stdout, failing loudly on error."""
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def pinned_objects(manifests: Iterable[Path]) -> dict[str, dict[str, str]]:
    """Every distinct pinned checksum across ``manifests``, with what is known about it.

    Two entries pinning identical bytes share one key; the first seen supplies
    the media type and the cache location.
    """
    objects: dict[str, dict[str, str]] = {}
    for manifest in manifests:
        lock = json.loads(manifest.with_suffix(".lock.json").read_text(encoding="utf-8"))
        for entry in lock["assets"]:
            checksum = entry["provenance"]["checksum"]
            objects.setdefault(
                checksum,
                {
                    "dataset_id": entry["asset"]["dataset_id"],
                    "asset_id": entry["asset"]["id"],
                    "media_type": entry["asset"].get("media_type") or "application/octet-stream",
                    "manifest": manifest.relative_to(ROOT).as_posix()
                    if manifest.is_relative_to(ROOT)
                    else str(manifest),
                },
            )
    return objects


def missing_objects(
    objects: dict[str, dict[str, str]], public_url: str, client: httpx.Client
) -> list[str]:
    """The pinned checksums the mirror does not serve yet, by a HEAD on each public URL."""
    from usdata.mirror import object_url

    missing = []
    for checksum in objects:
        response = client.head(object_url(public_url, checksum))
        if response.status_code == 404:
            missing.append(checksum)
        elif response.status_code != 200:
            response.raise_for_status()
    return missing


def upload(
    manifests: list[Path],
    cache: Path,
    *,
    public_url: str = PUBLIC_URL,
    bucket: str = BUCKET,
    dry_run: bool = False,
    run: Run = run,
    client: httpx.Client | None = None,
) -> list[str]:
    """Upload every pinned object the mirror lacks; return the checksums uploaded."""
    from usdata.cache import cached_path, sha256_file
    from usdata.mirror import object_key

    objects = pinned_objects(manifests)
    with client or httpx.Client(follow_redirects=True) as http:
        missing = missing_objects(objects, public_url, http)
    print(f"{len(objects)} pinned objects; {len(missing)} not on the mirror", flush=True)
    uploaded: list[str] = []
    for checksum in missing:
        info = objects[checksum]
        path = cached_path(info["dataset_id"], info["asset_id"], cache)
        if not path.is_file():
            raise FileNotFoundError(f"{info['asset_id']} is not in {cache}; restore it first")
        if (found := sha256_file(path)) != checksum:
            raise ValueError(f"{path} holds {found}, not the pinned {checksum}")
        key = object_key(checksum)
        print(
            f"{'would upload' if dry_run else 'uploading'} {key} <- {info['asset_id']}", flush=True
        )
        if dry_run:
            continue
        run(
            [
                "aws",
                "s3api",
                "put-object",
                "--bucket",
                bucket,
                "--key",
                key,
                "--body",
                str(path),
                "--content-type",
                info["media_type"],
                "--cache-control",
                IMMUTABLE,
            ]
        )
        uploaded.append(checksum)
    return uploaded


def list_keys(bucket: str, run: Run) -> list[str]:
    """Every key under the mirror prefix, through the CLI's own pagination."""
    out = run(
        [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            bucket,
            "--prefix",
            PREFIX,
            "--query",
            "Contents[].Key",
            "--output",
            "json",
        ]
    )
    keys = json.loads(out or "null") or []
    return sorted(key for key in keys if isinstance(key, str))


def prune(
    manifests: list[Path], *, bucket: str = BUCKET, delete: bool = False, run: Run = run
) -> list[str]:
    """Keys no committed lockfile pins; deleted only with ``delete``. Returns them."""
    from usdata.mirror import object_key

    referenced = {object_key(checksum) for checksum in pinned_objects(manifests)}
    unreferenced = [key for key in list_keys(bucket, run) if key not in referenced]
    print(
        f"{len(referenced)} keys pinned by {len(manifests)} lockfiles; "
        f"{len(unreferenced)} unreferenced",
        flush=True,
    )
    for key in unreferenced:
        print(f"{'deleting' if delete else 'would delete'} {key}", flush=True)
        if delete:
            run(["aws", "s3api", "delete-object", "--bucket", bucket, "--key", key])
    return unreferenced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    up = commands.add_parser("upload", help="upload pinned objects the mirror lacks")
    up.add_argument("--manifest", action="append", default=[], help="pinned example slug or path")
    up.add_argument("--cache", type=Path, required=True, help="cache a restore filled")
    up.add_argument("--public-url", default=PUBLIC_URL)
    up.add_argument("--bucket", default=BUCKET)
    up.add_argument("--dry-run", action="store_true")
    pr = commands.add_parser("prune", help="list, or delete, keys no committed lockfile pins")
    pr.add_argument("--bucket", default=BUCKET)
    pr.add_argument("--delete", action="store_true", help="actually delete; default is a plan")
    args = parser.parse_args()
    manifests = pinned_manifests()
    if args.command == "upload" and args.manifest:
        try:
            manifests = resolve_manifests(args.manifest, manifests)
        except ValueError as exc:
            parser.error(str(exc))
    if not manifests:
        parser.error("No pinned examples found")
    try:
        if args.command == "upload":
            uploaded = upload(
                manifests,
                args.cache.resolve(),
                public_url=args.public_url,
                bucket=args.bucket,
                dry_run=args.dry_run,
            )
            print(f"{len(uploaded)} object(s) uploaded")
        else:
            prune(manifests, bucket=args.bucket, delete=args.delete)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
        detail = getattr(exc, "stderr", "") or ""
        sys.exit(f"{exc}\n{detail}".rstrip())


if __name__ == "__main__":
    main()

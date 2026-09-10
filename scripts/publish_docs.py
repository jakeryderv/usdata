"""Validate a released documentation archive and atomically publish it to private R2."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import re
from pathlib import Path
from urllib.request import urlopen

import boto3
from botocore.config import Config

MAX_BYTES = 24 * 1024 * 1024
CATALOG = "docs/catalog.json"


def version_key(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("expected a stable package version")
    return tuple(map(int, version.split(".")))


def validate(descriptor: Path, version: str, package_commit: str, docs_commit: str):
    if version_key(version) < (0, 10, 0):
        raise ValueError("hosted documentation starts at 0.10.0")
    if any(not re.fullmatch(r"[a-f0-9]{40}", sha) for sha in (package_commit, docs_commit)):
        raise ValueError("expected full source commit IDs")
    info = json.loads(descriptor.read_text())
    if any(
        info.get(key) != value
        for key, value in {
            "schema": 1,
            "version": version,
            "package_commit": package_commit,
            "docs_commit": docs_commit,
        }.items()
    ):
        raise ValueError("descriptor does not match requested source identity")
    bundle = info["bundle"]
    if bundle["name"] != f"usdata-docs-{docs_commit}.ndjson.gz":
        raise ValueError("unexpected bundle name")
    path = descriptor.parent / bundle["name"]
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("compressed archive exceeds size limit")
    compressed = path.read_bytes()
    if (
        len(compressed) != bundle["size"]
        or hashlib.sha256(compressed).hexdigest() != bundle["sha256"]
    ):
        raise ValueError("bundle checksum or size mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("expanded archive exceeds size limit")
    rows = [json.loads(line) for line in raw.splitlines()]
    if not 1 <= len(rows) <= 500 or len(rows) != info["files"]:
        raise ValueError("unexpected file count")
    seen = set()
    files = []
    for row in rows:
        name = row["path"]
        if (
            not isinstance(name, str)
            or re.search(r"[\\\x00-\x1f\x7f?#%]", name)
            or any(part in ("", ".", "..") for part in name.split("/"))
            or name in seen
        ):
            raise ValueError("unsafe or duplicate archive path")
        seen.add(name)
        body = base64.b64decode(row["data"], validate=True)
        if hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise ValueError("file checksum mismatch")
        if not isinstance(row["type"], str) or not re.fullmatch(r"[\x20-\x7e]+", row["type"]):
            raise ValueError("invalid content type")
        files.append((name, body, row["type"]))
    if not {"index.html", "404.html"} <= seen:
        raise ValueError("incomplete archive: index.html and 404.html required")
    snapshot = {key: info[key] for key in ("version", "package_commit", "docs_commit")}
    snapshot.update(revision=bundle["sha256"], prefix=f"docs/{version}/{bundle['sha256']}/")
    return snapshot, files


def put(client, bucket: str, key: str, body: bytes, content_type: str, **conditions):
    # Explicit Content-MD5 is supported by R2 and verifies each upload in transit.
    return client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
        ContentMD5=base64.b64encode(hashlib.md5(body, usedforsecurity=False).digest()).decode(),
        Metadata={"sha256": hashlib.sha256(body).hexdigest()},
        **conditions,
    )


def publish(client, bucket: str, snapshot: dict, files: list):
    try:
        obj = client.get_object(Bucket=bucket, Key=CATALOG)
    except client.exceptions.NoSuchKey:
        catalog = {"schema": 1, "current": None, "versions": {}}
        condition = {"IfNoneMatch": "*"}
    else:
        with obj["Body"] as stream:
            catalog = json.loads(stream.read())
        condition = {"IfMatch": obj["ETag"]}
    if catalog.get("schema") != 1 or not isinstance(catalog.get("versions"), dict):
        raise ValueError("invalid existing catalog")
    version = snapshot["version"]
    if catalog["versions"].get(version) == snapshot:
        print(f"Documentation {version} is already at revision {snapshot['revision']}")
        return
    for name, body, content_type in files:
        put(client, bucket, snapshot["prefix"] + name, body, content_type)
    catalog["versions"][version] = snapshot
    catalog["current"] = max(catalog["versions"], key=version_key)
    # Never overwrite a catalog changed by another publisher. A conflict fails visibly;
    # inspect the winning revision, then retry this exact archive if still appropriate.
    put(client, bucket, CATALOG, json.dumps(catalog).encode(), "application/json", **condition)
    print(f"Published {len(files)} files for {version}, revision {snapshot['revision']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("descriptor", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--package-commit", required=True)
    parser.add_argument("--docs-commit", required=True)
    parser.add_argument("--bucket", default="usdata")
    args = parser.parse_args()
    snapshot, files = validate(args.descriptor, args.version, args.package_commit, args.docs_commit)
    # R2 writes are authorized only after confirming the package is publicly available.
    with urlopen(f"https://pypi.org/pypi/usdata/{args.version}/json", timeout=30) as response:
        package = json.load(response)
    if package["info"]["version"] != args.version or not package["urls"]:
        raise ValueError("package is not published on PyPI")
    client = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(
            connect_timeout=10,
            read_timeout=60,
            retries={"mode": "standard", "total_max_attempts": 3},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
    try:
        publish(client, args.bucket, snapshot, files)
    finally:
        client.close()


if __name__ == "__main__":
    main()

import base64
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.stub import Stubber

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("publish_docs", ROOT / "scripts/publish_docs.py")
assert spec and spec.loader
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


@pytest.fixture
def archive(tmp_path):
    rows = [
        {
            "path": name,
            "data": base64.b64encode(body).decode(),
            "sha256": hashlib.sha256(body).hexdigest(),
            "type": "text/html",
        }
        for name, body in [("index.html", b"home"), ("404.html", b"missing")]
    ]

    def write(records=rows):
        body = gzip.compress(b"\n".join(json.dumps(row).encode() for row in records))
        name = f"usdata-docs-{'b' * 40}.ndjson.gz"
        (tmp_path / name).write_bytes(body)
        descriptor = tmp_path / "descriptor.json"
        descriptor.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "version": "0.10.0",
                    "package_commit": "a" * 40,
                    "docs_commit": "b" * 40,
                    "files": len(records),
                    "bundle": {
                        "name": name,
                        "size": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                    },
                }
            )
        )
        return descriptor

    return write, rows


def validate(path):
    return publisher.validate(path, "0.10.0", "a" * 40, "b" * 40)


@pytest.mark.parametrize("failure", ["checksum", "traversal", "duplicate", "missing", "identity"])
def test_invalid_archives_fail_before_publication(archive, failure):
    write, rows = archive
    if failure == "checksum":
        rows[1]["sha256"] = "0" * 64
    elif failure == "traversal":
        rows[1]["path"] = "../404.html"
    elif failure == "duplicate":
        rows[1]["path"] = "index.html"
    elif failure == "missing":
        rows.pop()
    path = write()
    if failure == "identity":
        path.write_text(path.read_text().replace('"a' + "a" * 39 + '"', '"c' + "c" * 39 + '"'))
    with pytest.raises(ValueError):
        validate(path)


@pytest.fixture
def client():
    s3: Any = boto3.client(
        "s3", region_name="auto", aws_access_key_id="test", aws_secret_access_key="test"
    )
    try:
        yield s3
    finally:
        s3.close()


def expect_put(stub, key, body, content_type="text/html", **condition):
    stub.add_response(
        "put_object",
        {},
        {
            "Bucket": "usdata",
            "Key": key,
            "Body": body,
            "ContentType": content_type,
            "ContentMD5": base64.b64encode(
                hashlib.md5(body, usedforsecurity=False).digest()
            ).decode(),
            "Metadata": {"sha256": hashlib.sha256(body).hexdigest()},
            **condition,
        },
    )


def test_publish_preserves_newer_version_and_is_idempotent(client, archive):
    snapshot, files = validate(archive[0]())
    catalog = {"schema": 1, "current": "0.11.0", "versions": {"0.11.0": {"revision": "old"}}}
    with Stubber(client) as stub:
        stub.add_response(
            "get_object", {"Body": io.BytesIO(json.dumps(catalog).encode()), "ETag": '"prior"'}
        )
        for name, body, content_type in files:
            expect_put(stub, snapshot["prefix"] + name, body, content_type)
        catalog["versions"]["0.10.0"] = snapshot
        expect_put(
            stub,
            publisher.CATALOG,
            json.dumps(catalog).encode(),
            "application/json",
            IfMatch='"prior"',
        )
        publisher.publish(client, "usdata", snapshot, files)
        stub.add_response(
            "get_object", {"Body": io.BytesIO(json.dumps(catalog).encode()), "ETag": '"next"'}
        )
        publisher.publish(client, "usdata", snapshot, files)
        stub.assert_no_pending_responses()


def test_first_publication_uses_conditional_create(client, archive):
    snapshot, files = validate(archive[0]())
    with Stubber(client) as stub:
        stub.add_client_error("get_object", "NoSuchKey", http_status_code=404)
        for name, body, content_type in files:
            expect_put(stub, snapshot["prefix"] + name, body, content_type)
        catalog = {"schema": 1, "current": "0.10.0", "versions": {"0.10.0": snapshot}}
        expect_put(
            stub,
            publisher.CATALOG,
            json.dumps(catalog).encode(),
            "application/json",
            IfNoneMatch="*",
        )
        publisher.publish(client, "usdata", snapshot, files)
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("conflict", [False, True])
def test_failed_upload_or_catalog_conflict_never_overwrites_catalog(client, archive, conflict):
    snapshot, files = validate(archive[0]())
    with Stubber(client) as stub:
        catalog = {"schema": 1, "current": "0.10.0", "versions": {"0.10.0": {"revision": "old"}}}
        stub.add_response(
            "get_object", {"Body": io.BytesIO(json.dumps(catalog).encode()), "ETag": '"prior"'}
        )
        if conflict:
            for name, body, content_type in files:
                expect_put(stub, snapshot["prefix"] + name, body, content_type)
        code = "PreconditionFailed" if conflict else "AccessDenied"
        stub.add_client_error("put_object", code, http_status_code=412 if conflict else 403)
        with pytest.raises(client.exceptions.ClientError, match=code):
            publisher.publish(client, "usdata", snapshot, files)
        stub.assert_no_pending_responses()

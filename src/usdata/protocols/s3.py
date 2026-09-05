"""Anonymous access to public S3 buckets over plain HTTPS.

Uses the S3 REST API directly (ListObjectsV2 + GET) so public open-data
buckets need no AWS SDK or credentials. Not suitable for private buckets.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from usdata.protocols import http

NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class S3Object(BaseModel):
    key: str
    size: int
    etag: str | None = None
    last_modified: datetime | None = None


def parse_s3_url(url: str) -> tuple[str, str]:
    if not url.startswith("s3://"):
        raise ValueError(f"not an s3:// URL: {url}")
    bucket, _, key = url[5:].partition("/")
    return bucket, key


def https_url(bucket: str, key: str = "") -> str:
    return f"https://{bucket}.s3.amazonaws.com/{quote(key)}"


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(NS + tag)
    return child.text if child is not None else None


def list_objects(
    bucket: str,
    prefix: str,
    client: httpx.Client | None = None,
    page_size: int = 1000,
) -> Iterator[S3Object]:
    """Yield every object under ``prefix``, following continuation tokens."""
    own = client is None
    client = client or http.client()
    params: dict[str, str | int] = {"list-type": 2, "prefix": prefix, "max-keys": page_size}
    try:
        while True:
            resp = client.get(https_url(bucket), params=params)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            for contents in root.iter(NS + "Contents"):
                key = _text(contents, "Key")
                if key is None:
                    continue
                etag = _text(contents, "ETag")
                modified = _text(contents, "LastModified")
                yield S3Object(
                    key=key,
                    size=int(_text(contents, "Size") or 0),
                    etag=etag.strip('"') if etag else None,
                    last_modified=datetime.fromisoformat(modified) if modified else None,
                )
            token = _text(root, "NextContinuationToken")
            if _text(root, "IsTruncated") != "true" or not token:
                return
            params["continuation-token"] = token
    finally:
        if own:
            client.close()


def download(url: str, dest: Path, client: httpx.Client | None = None) -> Path:
    """Download an ``s3://bucket/key`` object anonymously."""
    bucket, key = parse_s3_url(url)
    return http.download(https_url(bucket, key), dest, client)

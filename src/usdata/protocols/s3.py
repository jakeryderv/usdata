"""Anonymous access to public S3 buckets over plain HTTPS.

Uses the S3 REST API directly (ListObjectsV2 + GET) so public open-data
buckets need no AWS SDK or credentials. Not suitable for private buckets.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from usdata.protocols import http

NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class S3Object(BaseModel):
    """One key from a bucket listing."""

    key: str
    size: int
    etag: str | None = None
    last_modified: datetime | None = None


def parse_s3_url(url: str) -> tuple[str, str]:
    """Split 's3://bucket/key' into (bucket, key)."""
    if not url.startswith("s3://"):
        raise ValueError(f"not an s3:// URL: {url}")
    bucket, _, key = url[5:].partition("/")
    return bucket, key


def https_url(bucket: str, key: str = "") -> str:
    """The virtual-hosted HTTPS URL for a bucket key, with the key percent-encoded."""
    return f"https://{bucket}.s3.amazonaws.com/{quote(key)}"


def object_url(url: str) -> str:
    """The HTTPS URL for an ``s3://bucket/key`` object, for any request, not only a download.

    Sidecars such as a GRIB2 ``<key>.idx`` index are ordinary keys, so they are
    reached through the same anonymous mapping the objects themselves use.
    """
    return https_url(*parse_s3_url(url))


def head_object(url: str, client: httpx.Client | None = None) -> S3Object:
    """Size, ETag, and last-modified of one ``s3://bucket/key`` object, without its bytes."""
    own = client is None
    client = client or http.client()
    try:
        response = http.head(object_url(url), client)
    finally:
        if own:
            client.close()
    modified = response.headers.get("Last-Modified")
    etag = response.headers.get("ETag")
    return S3Object(
        key=parse_s3_url(url)[1],
        size=int(response.headers.get("Content-Length", 0)),
        etag=etag.strip('"') if etag else None,
        last_modified=parsedate_to_datetime(modified) if modified else None,
    )


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
    seen_tokens: set[str] = set()
    try:
        while True:
            resp = http.get(https_url(bucket), client, params=params)
            root = ET.fromstring(resp.text)
            truncated = _text(root, "IsTruncated") == "true"
            token = _text(root, "NextContinuationToken")
            if truncated:
                if not token or not token.strip():
                    raise httpx.RemoteProtocolError(
                        "Truncated S3 listing has no continuation token", request=resp.request
                    )
                if token in seen_tokens:
                    raise httpx.RemoteProtocolError(
                        "S3 listing repeated a continuation token", request=resp.request
                    )
                seen_tokens.add(token)
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
            if not truncated:
                return
            assert token is not None
            params["continuation-token"] = token
    finally:
        if own:
            client.close()


def download(url: str, dest: Path, client: httpx.Client | None = None) -> Path:
    """Download an ``s3://bucket/key`` object anonymously."""
    return http.download(object_url(url), dest, client)

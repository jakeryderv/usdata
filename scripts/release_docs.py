"""Build release-specific docs and portable archives; never publish or create tags."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 24 * 1024 * 1024


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def export(ref: str, target: Path, *paths: str) -> None:
    data = subprocess.check_output(["git", "archive", ref, *paths], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(target, filter="data")


def package_site(site: Path, output: Path, version: str, package_sha: str, docs_sha: str) -> Path:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("expected a stable package version")
    if any(not re.fullmatch(r"[a-f0-9]{40}", sha) for sha in (package_sha, docs_sha)):
        raise ValueError("expected full source commit IDs")
    paths = sorted(path for path in site.rglob("*") if path.is_file())
    if not 1 <= len(paths) <= 500 or not all(
        (site / p).is_file() for p in ("index.html", "404.html")
    ):
        raise ValueError("site needs index.html, 404.html, and at most 500 files")
    output.mkdir(parents=True, exist_ok=True)
    stem = f"usdata-docs-{docs_sha}"
    lines = []
    with zipfile.ZipFile(output / f"{stem}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            name = path.relative_to(site).as_posix()
            if path.is_symlink() or re.search(r"[\\\x00-\x1f?#%]", name):
                raise ValueError(f"unsafe site path: {name}")
            body = path.read_bytes()
            archive.writestr(name, body)
            lines.append(
                json.dumps(
                    {
                        "path": name,
                        "data": base64.b64encode(body).decode(),
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "type": mimetypes.guess_type(name)[0] or "application/octet-stream",
                    },
                    separators=(",", ":"),
                )
            )
    raw = ("\n".join(lines) + "\n").encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("site exceeds the bounded publication size")
    bundle = output / f"{stem}.ndjson.gz"
    bundle.write_bytes(gzip.compress(raw, mtime=0))
    descriptor = {
        "schema": 1,
        "version": version,
        "package_commit": package_sha,
        "docs_commit": docs_sha,
        "files": len(paths),
        "bundle": {
            "name": bundle.name,
            "size": bundle.stat().st_size,
            "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        },
    }
    result = output / f"{stem}.json"
    result.write_text(json.dumps(descriptor, indent=2) + "\n")
    return result


def build(package_ref: str, docs_ref: str, output: Path) -> Path:
    package_sha = git("rev-parse", f"{package_ref}^{{commit}}")
    docs_sha = git("rev-parse", f"{docs_ref}^{{commit}}")
    version = tomllib.loads(git("show", f"{package_sha}:pyproject.toml"))["project"]["version"]
    with tempfile.TemporaryDirectory(prefix="usdata-docs-") as directory:
        checkout = Path(directory)
        export(docs_sha, checkout)
        shutil.rmtree(checkout / "src")
        export(package_sha, checkout, "src")
        project = checkout / "pyproject.toml"
        project.write_text(
            re.sub(
                r'(?m)^version = "[^"]+"', f'version = "{version}"', project.read_text(), count=1
            )
        )
        environment = dict(os.environ, USDATA_DOCS_VERSION=version)
        environment.pop("UV_PROJECT_ENVIRONMENT", None)
        # Resolve only the temporary project's version change; use the recorded docs toolchain.
        subprocess.run(["uv", "lock", "--offline"], cwd=checkout, env=environment, check=True)
        subprocess.run(
            [
                "uv",
                "run",
                "--locked",
                "--group",
                "docs",
                "--no-default-groups",
                "python",
                "scripts/docs_site.py",
                "build",
            ],
            cwd=checkout,
            env=environment,
            check=True,
        )
        return package_site(checkout / "site", output, version, package_sha, docs_sha)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-ref", default="HEAD")
    parser.add_argument("--docs-ref", default="HEAD")
    parser.add_argument("--output", type=Path, default=ROOT / ".build/release-docs")
    args = parser.parse_args()
    print(build(args.package_ref, args.docs_ref, args.output.resolve()))


if __name__ == "__main__":
    main()

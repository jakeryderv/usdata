import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("site_archive", ROOT / "scripts/site_archive.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_archive_keeps_assets_and_adds_notice_without_overwriting_current_site(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("current home")
    module.install_archive(site)
    assert (site / "index.html").read_text() == "current home"
    with zipfile.ZipFile(module.ARCHIVE) as archive:
        for name in archive.namelist():
            output = (site / "0.10.0" / name).read_bytes()
            if name.endswith(".html"):
                assert module.BANNER.encode() in output
                assert output.replace(module.BANNER.encode(), b"", 1) == archive.read(name)
            else:
                assert output == archive.read(name)


@pytest.mark.parametrize("fault", ["checksum", "traversal", "missing"])
def test_invalid_archive_fails_before_writing_files(tmp_path, fault):
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("index.html", "<body>test</body>")
        if fault != "missing":
            output.writestr("404.html", "<body>missing</body>")
        if fault == "traversal":
            output.writestr("../escape", "bad")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    site = tmp_path / "site"
    with pytest.raises(ValueError):
        module.install_archive(site, archive, "0" * 64 if fault == "checksum" else digest)
    assert not site.exists()

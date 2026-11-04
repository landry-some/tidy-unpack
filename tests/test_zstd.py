import io
import shutil
import tarfile

import pytest

from tidy_unpack import archive
from tidy_unpack.archive import (
    Entry,
    UnsupportedArchive,
    detect_format,
    open_archive,
    strip_archive_suffix,
)
from tidy_unpack.extract import unpack

zstd = pytest.importorskip("compression.zstd", reason="needs Python 3.14 to write zstd")
needs_zstd_command = pytest.mark.skipif(shutil.which("zstd") is None, reason="no zstd command")


def make_tar_zst(path):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as t:
        info = tarfile.TarInfo("p/a.txt")
        info.size = 1
        t.addfile(info, io.BytesIO(b"A"))
    path.write_bytes(zstd.compress(raw.getvalue()))
    return path


@pytest.fixture(params=["module", "command"])
def zstd_backend(request, monkeypatch):
    """Run the test with compression.zstd and again with the zstd command."""
    if request.param == "command":
        if shutil.which("zstd") is None:
            pytest.skip("no zstd command")
        monkeypatch.setattr(archive, "_zstd", None)
    return request.param


def test_tar_zst(tmp_path, zstd_backend):
    path = make_tar_zst(tmp_path / "app.tar.zst")
    assert detect_format(path) == "zst"
    with open_archive(path) as arc:
        assert arc.format == "tar"
        assert arc.entries == [Entry("p/a.txt", "file")]
        assert arc.read(arc.entries[0]).read() == b"A"


def test_single_zst_file(tmp_path, zstd_backend):
    path = tmp_path / "notes.txt.zst"
    path.write_bytes(zstd.compress(b"hello"))
    with open_archive(path) as arc:
        assert arc.format == "zst"
        assert arc.entries == [Entry("notes.txt", "file")]
        with arc.read(arc.entries[0]) as f:
            assert f.read() == b"hello"


def test_zst_suffixes():
    assert strip_archive_suffix("app.tar.zst") == "app"
    assert strip_archive_suffix("app.tzst") == "app"
    assert strip_archive_suffix("notes.txt.zst") == "notes.txt"


def test_zst_without_module_or_command(tmp_path, monkeypatch):
    path = make_tar_zst(tmp_path / "app.tar.zst")
    monkeypatch.setattr(archive, "_zstd", None)
    monkeypatch.setattr(archive.shutil, "which", lambda name: None)
    with pytest.raises(UnsupportedArchive, match="needs Python 3.14\\+ or the zstd command"):
        open_archive(path)


@needs_zstd_command
def test_damaged_zst_with_command(tmp_path, monkeypatch):
    path = tmp_path / "bad.tar.zst"
    path.write_bytes(b"\x28\xb5\x2f\xfd" + b"junk")
    monkeypatch.setattr(archive, "_zstd", None)
    with pytest.raises(UnsupportedArchive, match="damaged zst"):
        open_archive(path)


def test_unpack_tar_zst(tmp_path, zstd_backend):
    path = make_tar_zst(tmp_path / "app.tar.zst")
    out = tmp_path / "out"
    out.mkdir()
    result = unpack(path, out)
    assert result.path == out / "app"
    assert (result.path / "a.txt").read_bytes() == b"A"

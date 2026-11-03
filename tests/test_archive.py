import bz2
import gzip
import lzma

import pytest

from tidy_unpack.archive import (
    Entry,
    UnsupportedArchive,
    clean_name,
    detect_format,
    open_archive,
    strip_archive_suffix,
)


@pytest.mark.parametrize(
    "filename, stem",
    [
        ("app-1.2.tar.gz", "app-1.2"),
        ("APP.TGZ", "APP"),
        ("a.tar.xz", "a"),
        ("a.tbz2", "a"),
        ("photos.zip", "photos"),
        ("notes.txt.gz", "notes.txt"),
        ("noext", "noext"),
        (".zip", ".zip"),
    ],
)
def test_strip_archive_suffix(filename, stem):
    assert strip_archive_suffix(filename) == stem


def test_clean_name():
    assert clean_name("./a/b/") == "a/b"
    assert clean_name("dir\\file.txt") == "dir/file.txt"
    assert clean_name("./") == ""


def test_detect_by_content_not_extension(tmp_path, zip_factory, tar_factory):
    assert detect_format(zip_factory("really-a-zip.tar.gz", {"a": b"1"})) == "zip"
    assert detect_format(tar_factory("t.zip", {"a": b"1"}, mode="w:xz")) == "tar"
    assert detect_format(tar_factory("plain", {"a": b"1"}, mode="w")) == "tar"


@pytest.mark.parametrize(
    "fmt, opener", [("gz", gzip.open), ("bz2", bz2.open), ("xz", lzma.open)]
)
def test_single_compressed_file(tmp_path, fmt, opener):
    path = tmp_path / f"notes.txt.{fmt}"
    with opener(path, "wb") as f:
        f.write(b"hello")
    assert detect_format(path) == fmt
    with open_archive(path) as arc:
        assert arc.entries == [Entry("notes.txt", "file")]
        assert arc.read(arc.entries[0]).read() == b"hello"


def test_unknown_format(tmp_path):
    path = tmp_path / "x.zip"
    path.write_bytes(b"just some text, not an archive")
    with pytest.raises(UnsupportedArchive):
        detect_format(path)


def test_zip_entries(zip_factory):
    path = zip_factory(
        "p.zip", {"p/": b"", "p/a.txt": b"A", "p/sub/b.txt": b"B"}, symlinks={"p/l": "a.txt"}
    )
    with open_archive(path) as arc:
        assert arc.format == "zip"
        assert arc.entries == [
            Entry("p", "dir"),
            Entry("p/a.txt", "file"),
            Entry("p/sub/b.txt", "file"),
            Entry("p/l", "symlink", "a.txt"),
        ]
        assert arc.read(arc.entries[2]).read() == b"B"


def test_tar_entries(tar_factory):
    path = tar_factory("p.tar.gz", {"./p/": b"", "./p/a.txt": b"A"}, symlinks={"p/l": "a.txt"})
    with open_archive(path) as arc:
        assert arc.format == "tar"
        assert arc.entries == [
            Entry("p", "dir"),
            Entry("p/a.txt", "file"),
            Entry("p/l", "symlink", "a.txt"),
        ]
        assert arc.read(arc.entries[1]).read() == b"A"


def test_damaged_zip(tmp_path):
    path = tmp_path / "bad.zip"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 30)
    with pytest.raises(UnsupportedArchive, match="damaged zip"):
        open_archive(path)

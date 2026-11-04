import io
import os
import stat
import tarfile
import time
import zipfile

import pytest

from tidy_unpack import extract
from tidy_unpack.archive import Entry
from tidy_unpack.extract import UnsafeArchive, check_link, check_name, unique_path, unpack


def tree(root):
    """Sorted relative paths under root, dirs with a trailing slash."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        for d in dirnames:
            out.append(os.path.normpath(os.path.join(rel, d)) + "/")
        for f in filenames:
            out.append(os.path.normpath(os.path.join(rel, f)))
    return sorted(out)


@pytest.fixture
def dest(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    return d


def test_collapses_wrapper_folder(dest, tar_factory):
    arc = tar_factory("app-1.2.tar.gz", {"app-1.2/": b"", "app-1.2/a": b"A", "app-1.2/s/b": b"B"})
    result = unpack(arc, dest)
    assert result.path == dest / "app-1.2"
    assert tree(result.path) == ["a", "s/", "s/b"]
    assert (result.path / "s" / "b").read_bytes() == b"B"


def test_wraps_tarbomb(dest, zip_factory):
    arc = zip_factory("bomb.zip", {"a.txt": b"1", "b.txt": b"2"})
    result = unpack(arc, dest)
    assert result.path == dest / "bomb"
    assert tree(dest) == ["bomb/", "bomb/a.txt", "bomb/b.txt"]


def test_lone_file(dest, zip_factory):
    arc = zip_factory("dl.zip", {"report.pdf": b"%PDF"})
    assert unpack(arc, dest).path == dest / "report.pdf"
    assert (dest / "report.pdf").read_bytes() == b"%PDF"


def test_never_overwrites(dest, zip_factory):
    (dest / "bomb").mkdir()
    (dest / "report.pdf").write_bytes(b"mine")
    arc = zip_factory("bomb.zip", {"a": b"1", "b": b"2"})
    assert unpack(arc, dest).path == dest / "bomb-2"
    assert unpack(arc, dest).path == dest / "bomb-3"
    single = zip_factory("dl.zip", {"report.pdf": b"new"})
    assert unpack(single, dest).path == dest / "report-2.pdf"
    assert (dest / "report.pdf").read_bytes() == b"mine"


def test_unique_path_counts_broken_symlinks(tmp_path):
    os.symlink("missing", tmp_path / "x")
    assert unique_path(tmp_path, "x") == tmp_path / "x-2"
    assert unique_path(tmp_path, ".bashrc") == tmp_path / ".bashrc"


def test_unique_path_keeps_dotted_folder_names_whole(tmp_path):
    (tmp_path / "proj-1.0").mkdir()
    (tmp_path / "notes.txt").touch()
    (tmp_path / ".env").touch()
    assert unique_path(tmp_path, "proj-1.0") == tmp_path / "proj-1.0-2"
    assert unique_path(tmp_path, "notes.txt", is_file=True) == tmp_path / "notes-2.txt"
    assert unique_path(tmp_path, ".env", is_file=True) == tmp_path / ".env-2"


@pytest.mark.parametrize("name", ["/etc/passwd", "a/../../x", "..", "C:/win.ini"])
def test_rejects_unsafe_names(name):
    with pytest.raises(UnsafeArchive):
        check_name(Entry(name, "file"))


@pytest.mark.parametrize(
    "rel, target, ok",
    [
        ("l", "a.txt", True),
        ("sub/l", "../a.txt", True),
        ("l", "../a.txt", False),
        ("l", "/etc/passwd", False),
        ("sub/l", "../../x", False),
    ],
)
def test_link_targets(rel, target, ok):
    entry = Entry(rel, "symlink", target)
    if ok:
        check_link(entry, rel)
    else:
        with pytest.raises(UnsafeArchive):
            check_link(entry, rel)


def test_unsafe_archive_writes_nothing(dest, tar_factory):
    arc = tar_factory("evil.tar", {"ok.txt": b"1", "../escape.txt": b"x"}, mode="w")
    with pytest.raises(UnsafeArchive):
        unpack(arc, dest)
    assert tree(dest) == []
    assert not (dest.parent / "escape.txt").exists()


def test_link_escaping_after_collapse_is_rejected(dest, tar_factory):
    # "p/l -> ../x" stays inside the archive, but "p/" is collapsed away,
    # so in the output it would point next to the folder.
    arc = tar_factory("p.tar.gz", {"p/a": b"1"}, symlinks={"p/l": "../x"})
    with pytest.raises(UnsafeArchive):
        unpack(arc, dest)


def test_safe_symlink_is_created(dest, tar_factory):
    arc = tar_factory("p.tar.gz", {"p/a": b"1", "p/b": b"2"}, symlinks={"p/l": "a"})
    result = unpack(arc, dest)
    assert os.readlink(result.path / "l") == "a"
    assert (result.path / "l").read_bytes() == b"1"


def test_link_clashing_with_a_folder_is_skipped(dest, tar_factory):
    # The file "via/f" makes "via" a real folder, so the "via" link is skipped.
    arc = tar_factory("p.tar", {"p/real/": b"", "p/via/f": b"x"}, symlinks={"p/via": "real"}, mode="w")
    result = unpack(arc, dest)
    assert (result.path / "via" / "f").read_bytes() == b"x"
    assert not (result.path / "real" / "f").exists()  # files never go through links
    assert result.skipped == ["p/via (link clashes with another entry)"]


def test_mac_zip_junk_does_not_block_collapse(dest, zip_factory):
    arc = zip_factory(
        "p.zip",
        {"p/a.txt": b"1", "p/.DS_Store": b"", "__MACOSX/p/._a.txt": b""},
    )
    result = unpack(arc, dest)
    assert result.path == dest / "p"
    assert tree(result.path) == ["a.txt"]
    assert result.junk == 2


def test_keep_junk(dest, zip_factory):
    arc = zip_factory("p.zip", {"p/a.txt": b"1", "__MACOSX/p/._a.txt": b""})
    result = unpack(arc, dest, keep_junk=True)
    assert tree(result.path) == ["__MACOSX/", "__MACOSX/p/", "__MACOSX/p/._a.txt", "p/", "p/a.txt"]
    assert result.junk == 0


@pytest.mark.parametrize("error", [OSError("disk full"), KeyboardInterrupt()])
def test_failed_unpack_leaves_nothing_behind(dest, zip_factory, monkeypatch, error):
    arc = zip_factory("p.zip", {"p/a": b"1", "p/sub/b": b"2"}, symlinks={"p/l": "a"})
    real_write = extract._write_file
    calls = []

    def flaky_write(*args, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise error
        real_write(*args, **kw)

    monkeypatch.setattr(extract, "_write_file", flaky_write)
    with pytest.raises(type(error)):
        unpack(arc, dest)
    assert tree(dest) == []


def test_failed_single_file_is_removed(dest, zip_factory, monkeypatch):
    arc = zip_factory("dl.zip", {"report.pdf": b"%PDF"})

    def broken_write(arc, entry, out):
        out.write_bytes(b"half")
        raise OSError("read error")

    monkeypatch.setattr(extract, "_write_file", broken_write)
    with pytest.raises(OSError):
        unpack(arc, dest)
    assert tree(dest) == []


def test_failure_does_not_touch_existing_output(dest, zip_factory, monkeypatch):
    (dest / "report.pdf").write_bytes(b"mine")
    arc = zip_factory("dl.zip", {"report.pdf": b"new"})

    def broken_write(arc, entry, out):
        raise OSError("read error")

    monkeypatch.setattr(extract, "_write_file", broken_write)
    with pytest.raises(OSError):
        unpack(arc, dest)
    assert tree(dest) == ["report.pdf"]
    assert (dest / "report.pdf").read_bytes() == b"mine"


def _tar_member(t, name, mode, mtime, data=None):
    info = tarfile.TarInfo(name)
    info.mode, info.mtime = mode, mtime
    if data is None:
        info.type = tarfile.DIRTYPE
        t.addfile(info)
    else:
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))


def test_tar_keeps_permissions_and_mtimes(dest, tmp_path):
    arc = tmp_path / "p.tar"
    with tarfile.open(arc, "w") as t:
        _tar_member(t, "p", 0o755, 1_000_000)
        _tar_member(t, "p/bin", 0o555, 2_000_000)
        _tar_member(t, "p/bin/run", 0o4775, 3_000_000, b"#!/bin/sh\n")
        _tar_member(t, "p/secret", 0o400, 4_000_000, b"x")
    result = unpack(arc, dest)
    run = result.path / "bin" / "run"
    assert stat.S_IMODE(run.stat().st_mode) == 0o755  # setuid and group write dropped
    assert stat.S_IMODE((result.path / "secret").stat().st_mode) == 0o600
    assert stat.S_IMODE((result.path / "bin").stat().st_mode) == 0o755
    assert run.stat().st_mtime == 3_000_000
    assert (result.path / "bin").stat().st_mtime == 2_000_000


def test_zip_keeps_permissions_and_mtimes(dest, tmp_path):
    arc = tmp_path / "p.zip"
    with zipfile.ZipFile(arc, "w") as z:
        info = zipfile.ZipInfo("p/run", date_time=(2020, 5, 17, 12, 30, 0))
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o750) << 16
        z.writestr(info, b"x")
        dos = zipfile.ZipInfo("p/dos.txt", date_time=(2001, 1, 1, 0, 0, 0))
        dos.create_system = 0
        dos.external_attr = 0x20  # DOS "archive" flag, no Unix bits
        z.writestr(dos, b"y")
    result = unpack(arc, dest)
    run = result.path / "run"
    assert stat.S_IMODE(run.stat().st_mode) == 0o750
    assert run.stat().st_mtime == time.mktime((2020, 5, 17, 12, 30, 0, 0, 0, -1))
    umask = os.umask(0)
    os.umask(umask)
    assert stat.S_IMODE((result.path / "dos.txt").stat().st_mode) == 0o666 & ~umask
    assert (result.path / "dos.txt").stat().st_mtime == time.mktime((2001, 1, 1, 0, 0, 0, 0, 0, -1))


def test_lone_file_keeps_mtime(dest, tmp_path):
    arc = tmp_path / "dl.zip"
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr(zipfile.ZipInfo("report.pdf", date_time=(2019, 3, 1, 8, 0, 0)), b"%PDF")
    result = unpack(arc, dest)
    assert result.path.stat().st_mtime == time.mktime((2019, 3, 1, 8, 0, 0, 0, 0, -1))

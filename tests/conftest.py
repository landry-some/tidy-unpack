"""Helpers that build small archives in a temp dir, so no binary fixtures are checked in."""

import io
import stat
import tarfile
import zipfile

import pytest


def make_zip(path, files, symlinks=None):
    """files: {name: bytes}, a name ending in "/" is a directory."""
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
        for name, target in (symlinks or {}).items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, target)
    return path


def make_tar(path, files, symlinks=None, mode="w:gz"):
    with tarfile.open(path, mode) as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name.rstrip("/"))
            if name.endswith("/"):
                info.type = tarfile.DIRTYPE
                t.addfile(info)
            else:
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
        for name, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            t.addfile(info)
    return path


@pytest.fixture
def zip_factory(tmp_path):
    return lambda name, files, **kw: make_zip(tmp_path / name, files, **kw)


@pytest.fixture
def tar_factory(tmp_path):
    return lambda name, files, **kw: make_tar(tmp_path / name, files, **kw)

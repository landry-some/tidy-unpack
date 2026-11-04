"""Open an archive of any supported format and list its entries the same way."""

from __future__ import annotations

import bz2
import gzip
import lzma
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

try:
    from compression import zstd as _zstd  # Python 3.14+
except ImportError:
    _zstd = None

# Compound suffixes first, so "a.tar.gz" loses ".tar.gz" and not just ".gz".
ARCHIVE_SUFFIXES = (
    ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst",
    ".tgz", ".tbz2", ".tbz", ".txz", ".tzst",
    ".tar", ".zip", ".gz", ".bz2", ".xz", ".zst",
)

_STREAM_MAGIC = {
    b"\x1f\x8b": "gz",
    b"BZh": "bz2",
    b"\xfd7zXZ\x00": "xz",
    b"\x28\xb5\x2f\xfd": "zst",
}


class UnsupportedArchive(Exception):
    """The file is not an archive format tidyx can read."""


@dataclass(frozen=True)
class Entry:
    """One member of an archive.

    ``name`` is the path inside the archive with forward slashes and no
    leading "./" or trailing "/". ``kind`` is "file", "dir", "symlink" or
    "other" (devices, fifos). ``target`` is the link target for symlinks.
    ``mode`` (permission bits) and ``mtime`` are None when the archive
    doesn't record them; they don't count when comparing entries.
    """

    name: str
    kind: str
    target: str = ""
    mode: int | None = field(default=None, compare=False)
    mtime: float | None = field(default=None, compare=False)


def strip_archive_suffix(filename: str) -> str:
    """Return the archive's file name without its archive extension."""
    lower = filename.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if lower.endswith(suffix) and len(filename) > len(suffix):
            return filename[: -len(suffix)]
    return filename


def clean_name(raw: str) -> str:
    """Normalize a member name: forward slashes, no "./" prefix, no trailing "/"."""
    name = raw.replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def open_zstd(path: Path) -> IO[bytes]:
    """Open a zstd file decompressed, with ``compression.zstd`` or the zstd command."""
    if _zstd is not None:
        return _zstd.open(path, "rb")
    if shutil.which("zstd") is None:
        raise UnsupportedArchive(f"{path.name}: zstd needs Python 3.14+ or the zstd command")
    out = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["zstd", "-dcq", "--", str(path)], stdout=out, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        out.close()
        error = proc.stderr.decode(errors="replace").strip()
        raise UnsupportedArchive(f"{path.name}: damaged zst archive ({error})")
    out.seek(0)
    return out


_STREAM_OPENERS = {
    "gz": gzip.open,
    "bz2": bz2.open,
    "xz": lzma.open,
    "zst": lambda path, mode: open_zstd(path),
}


def detect_format(path: Path) -> str:
    """Return "zip", "tar", "gz", "bz2", "xz" or "zst" from the file's contents.

    zstd is checked before tar, so a .tar.zst is "zst" on every Python version.
    """
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        return "zip"
    if head.startswith(b"\x28\xb5\x2f\xfd"):
        return "zst"
    if tarfile.is_tarfile(path):
        return "tar"
    for magic, fmt in _STREAM_MAGIC.items():
        if head.startswith(magic):
            return fmt
    raise UnsupportedArchive(f"{path.name}: not a zip, tar, gzip, bzip2, xz or zstd file")


class Archive:
    """An opened archive. Use as a context manager."""

    format: str
    entries: list[Entry]

    def read(self, entry: Entry) -> IO[bytes]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> Archive:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class _ZipArchive(Archive):
    format = "zip"

    def __init__(self, path: Path) -> None:
        self._zip = zipfile.ZipFile(path)
        self._infos: dict[str, zipfile.ZipInfo] = {}
        self.entries = []
        for info in self._zip.infolist():
            name = clean_name(info.filename)
            if not name:
                continue
            mode = info.external_attr >> 16
            # Only zips made on Unix store permission bits.
            perms = stat.S_IMODE(mode) if info.create_system == 3 and mode else None
            # Zip times are local time, without a time zone.
            mtime = time.mktime(info.date_time + (0, 0, -1))
            if info.is_dir():
                entry = Entry(name, "dir", mode=perms, mtime=mtime)
            elif stat.S_ISLNK(mode):
                target = self._zip.read(info).decode("utf-8", "replace")
                entry = Entry(name, "symlink", target)
            else:
                entry = Entry(name, "file", mode=perms, mtime=mtime)
            self._infos[name] = info
            self.entries.append(entry)

    def read(self, entry: Entry) -> IO[bytes]:
        return self._zip.open(self._infos[entry.name])

    def close(self) -> None:
        self._zip.close()


class _TarArchive(Archive):
    format = "tar"

    def __init__(self, path: Path, fileobj: IO[bytes] | None = None) -> None:
        # tarfile leaves a passed-in fileobj open, so close it ourselves.
        self._fileobj = fileobj
        self._tar = tarfile.open(path, "r:*", fileobj=fileobj)
        self._members: dict[str, tarfile.TarInfo] = {}
        self.entries = []
        for member in self._tar.getmembers():
            name = clean_name(member.name)
            if not name:
                continue
            meta = {"mode": stat.S_IMODE(member.mode), "mtime": member.mtime}
            if member.isdir():
                entry = Entry(name, "dir", **meta)
            elif member.issym():
                entry = Entry(name, "symlink", member.linkname)
            elif member.isfile() or member.islnk():
                # Hard links are read through to their target's data.
                entry = Entry(name, "file", **meta)
            else:
                entry = Entry(name, "other")
            self._members[name] = member
            self.entries.append(entry)

    def read(self, entry: Entry) -> IO[bytes]:
        f = self._tar.extractfile(self._members[entry.name])
        if f is None:
            raise OSError(f"{entry.name}: no data in archive")
        return f

    def close(self) -> None:
        self._tar.close()
        if self._fileobj is not None:
            self._fileobj.close()


class _StreamArchive(Archive):
    """A single compressed file (.gz, .bz2, .xz, .zst) seen as a one-entry archive."""

    def __init__(self, path: Path, fmt: str) -> None:
        self.format = fmt
        self._path = path
        self._file: IO[bytes] | None = None
        name = strip_archive_suffix(path.name)
        if name == path.name:
            name += ".out"
        self.entries = [Entry(name, "file")]

    def read(self, entry: Entry) -> IO[bytes]:
        self._file = _STREAM_OPENERS[self.format](self._path, "rb")
        return self._file

    def close(self) -> None:
        if self._file is not None:
            self._file.close()


_ZSTD_ERRORS = (_zstd.ZstdError,) if _zstd is not None else ()


def _open_zst(path: Path) -> Archive:
    """A .tar.zst is read as a tar, anything else as one compressed file."""
    f = open_zstd(path)
    try:
        if tarfile.is_tarfile(f):
            return _TarArchive(path, f)
    except BaseException:
        f.close()
        raise
    f.close()
    return _StreamArchive(path, "zst")


def open_archive(path: Path) -> Archive:
    """Open ``path`` with the reader that matches its contents."""
    fmt = detect_format(path)
    try:
        if fmt == "zip":
            return _ZipArchive(path)
        if fmt == "tar":
            return _TarArchive(path)
        if fmt == "zst":
            return _open_zst(path)
        return _StreamArchive(path, fmt)
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, *_ZSTD_ERRORS) as e:
        raise UnsupportedArchive(f"{path.name}: damaged {fmt} archive ({e})") from e

"""Open an archive of any supported format and list its entries the same way."""

from __future__ import annotations

import bz2
import gzip
import lzma
import stat
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO

# Compound suffixes first, so "a.tar.gz" loses ".tar.gz" and not just ".gz".
ARCHIVE_SUFFIXES = (
    ".tar.gz", ".tar.bz2", ".tar.xz",
    ".tgz", ".tbz2", ".tbz", ".txz",
    ".tar", ".zip", ".gz", ".bz2", ".xz",
)

_STREAM_MAGIC = {
    b"\x1f\x8b": "gz",
    b"BZh": "bz2",
    b"\xfd7zXZ\x00": "xz",
}
_STREAM_OPENERS = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}


class UnsupportedArchive(Exception):
    """The file is not an archive format tidyx can read."""


@dataclass(frozen=True)
class Entry:
    """One member of an archive.

    ``name`` is the path inside the archive with forward slashes and no
    leading "./" or trailing "/". ``kind`` is "file", "dir", "symlink" or
    "other" (devices, fifos). ``target`` is the link target for symlinks.
    """

    name: str
    kind: str
    target: str = ""


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


def detect_format(path: Path) -> str:
    """Return "zip", "tar", "gz", "bz2" or "xz" from the file's contents."""
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        return "zip"
    if tarfile.is_tarfile(path):
        return "tar"
    for magic, fmt in _STREAM_MAGIC.items():
        if head.startswith(magic):
            return fmt
    raise UnsupportedArchive(f"{path.name}: not a zip, tar, gzip, bzip2 or xz file")


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
            if info.is_dir():
                entry = Entry(name, "dir")
            elif stat.S_ISLNK(mode):
                target = self._zip.read(info).decode("utf-8", "replace")
                entry = Entry(name, "symlink", target)
            else:
                entry = Entry(name, "file")
            self._infos[name] = info
            self.entries.append(entry)

    def read(self, entry: Entry) -> IO[bytes]:
        return self._zip.open(self._infos[entry.name])

    def close(self) -> None:
        self._zip.close()


class _TarArchive(Archive):
    format = "tar"

    def __init__(self, path: Path) -> None:
        self._tar = tarfile.open(path, "r:*")
        self._members: dict[str, tarfile.TarInfo] = {}
        self.entries = []
        for member in self._tar.getmembers():
            name = clean_name(member.name)
            if not name:
                continue
            if member.isdir():
                entry = Entry(name, "dir")
            elif member.issym():
                entry = Entry(name, "symlink", member.linkname)
            elif member.isfile() or member.islnk():
                # Hard links are read through to their target's data.
                entry = Entry(name, "file")
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


class _StreamArchive(Archive):
    """A single compressed file (.gz, .bz2, .xz) seen as a one-entry archive."""

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


def open_archive(path: Path) -> Archive:
    """Open ``path`` with the reader that matches its contents."""
    fmt = detect_format(path)
    try:
        if fmt == "zip":
            return _ZipArchive(path)
        if fmt == "tar":
            return _TarArchive(path)
        return _StreamArchive(path, fmt)
    except (zipfile.BadZipFile, tarfile.TarError, EOFError) as e:
        raise UnsupportedArchive(f"{path.name}: damaged {fmt} archive ({e})") from e

"""Write a planned layout to disk without escaping it or overwriting anything."""

from __future__ import annotations

import os
import posixpath
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .archive import Archive, Entry, open_archive, strip_archive_suffix
from .junk import drop_junk
from .layout import Layout, plan_layout

_DRIVE = re.compile(r"^[A-Za-z]:")


class UnsafeArchive(Exception):
    """The archive has an entry that would land outside the output folder."""


@dataclass
class Unpacked:
    path: Path
    skipped: list[str] = field(default_factory=list)
    junk: int = 0


def check_name(entry: Entry) -> None:
    """Reject absolute names and names with ".." components."""
    path = PurePosixPath(entry.name)
    if path.is_absolute() or _DRIVE.match(entry.name) or ".." in path.parts:
        raise UnsafeArchive(f"unsafe path in archive: {entry.name}")


def check_link(entry: Entry, rel: str) -> None:
    """Reject symlinks whose target would point outside the output folder."""
    target = entry.target
    if target.startswith("/") or _DRIVE.match(target):
        raise UnsafeArchive(f"absolute link target: {entry.name} -> {target}")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
    if resolved == ".." or resolved.startswith("../"):
        raise UnsafeArchive(f"link points outside the folder: {entry.name} -> {target}")


def unique_path(dest: Path, name: str, is_file: bool = False) -> Path:
    """Return ``dest/name``, or ``name-2``, ``name-3``... if it's already taken.

    For files the number goes before the extension (``report-2.pdf``); folder
    names are kept whole, since "proj-1.0" has no extension.
    """
    candidate = dest / name
    if not os.path.lexists(candidate):
        return candidate
    p = PurePosixPath(name)
    stem, suffix = (p.stem, p.suffix) if is_file and p.stem else (name, "")
    n = 2
    while os.path.lexists(candidate := dest / f"{stem}-{n}{suffix}"):
        n += 1
    return candidate


def prepare(arc: Archive, archive_path: Path, keep_junk: bool = False) -> tuple[Layout, int]:
    """Check every entry, drop junk unless asked not to, then plan where it goes.

    Returns the layout and the number of junk entries dropped.
    """
    for entry in arc.entries:
        check_name(entry)
    entries, junk = (arc.entries, 0) if keep_junk else drop_junk(arc.entries)
    layout = plan_layout(entries, strip_archive_suffix(archive_path.name))
    for entry, rel in layout.members:
        if entry.kind == "symlink":
            check_link(entry, rel)
    return layout, junk


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root)


def _write_file(arc: Archive, entry: Entry, out: Path, mode: str = "wb") -> None:
    with arc.read(entry) as src, open(out, mode) as dst:
        shutil.copyfileobj(src, dst)


def write_layout(arc: Archive, layout: Layout, dest: Path) -> Unpacked:
    """Create the layout's root under ``dest`` and fill it."""
    target = unique_path(dest, layout.root, layout.is_single_file)
    result = Unpacked(target)

    if layout.is_single_file:
        _write_file(arc, layout.members[0][0], target, "xb")
        return result

    target.mkdir()
    root = target.resolve()
    links = []
    for entry, rel in layout.members:
        out = target / rel
        # Symlinks are only created at the end, so nothing below follows one
        # from the archive, but check anyway in case the folder was tampered with.
        if not _inside(out.parent, root):
            raise UnsafeArchive(f"path leaves the folder: {entry.name}")
        if entry.kind == "dir":
            out.mkdir(parents=True, exist_ok=True)
        elif entry.kind == "file":
            out.parent.mkdir(parents=True, exist_ok=True)
            _write_file(arc, entry, out)
        elif entry.kind == "symlink":
            links.append((entry, out))
        else:
            result.skipped.append(f"{entry.name} (special file)")

    for entry, out in links:
        out.parent.mkdir(parents=True, exist_ok=True)
        if not _inside(out.parent, root):
            raise UnsafeArchive(f"path leaves the folder: {entry.name}")
        if os.path.lexists(out):
            result.skipped.append(f"{entry.name} (link clashes with another entry)")
            continue
        try:
            os.symlink(entry.target, out)
        except OSError as e:
            result.skipped.append(f"{entry.name} (could not create link: {e.strerror})")
    return result


def unpack(archive_path: Path, dest: Path, keep_junk: bool = False) -> Unpacked:
    """Unpack ``archive_path`` into one new item inside ``dest``."""
    with open_archive(archive_path) as arc:
        layout, junk = prepare(arc, archive_path, keep_junk)
        result = write_layout(arc, layout, dest)
    result.junk = junk
    return result

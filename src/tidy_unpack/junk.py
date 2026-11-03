"""Files that OS tools add to archives and nobody wants unpacked."""

from __future__ import annotations

from .archive import Entry

JUNK_DIRS = {"__MACOSX"}
JUNK_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def is_junk(name: str) -> bool:
    parts = name.split("/")
    if any(part in JUNK_DIRS for part in parts):
        return True
    base = parts[-1]
    # "._name" files are macOS resource forks (AppleDouble).
    return base in JUNK_FILES or base.startswith("._")


def drop_junk(entries: list[Entry]) -> tuple[list[Entry], int]:
    """Return the entries that aren't junk, and how many were dropped."""
    kept = [e for e in entries if not is_junk(e.name)]
    return kept, len(entries) - len(kept)

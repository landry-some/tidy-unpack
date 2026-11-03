"""Command-line entry point for tidyx."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .archive import UnsupportedArchive
from .extract import UnsafeArchive, unpack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tidyx",
        description="Unpack archives into exactly one clean folder each, in the current directory.",
    )
    parser.add_argument("archives", nargs="+", type=Path, metavar="ARCHIVE")
    parser.add_argument(
        "--keep-junk",
        action="store_true",
        help="keep __MACOSX/, .DS_Store, Thumbs.db, desktop.ini and ._* files",
    )
    return parser


def _shown(path: Path) -> str:
    name = os.path.relpath(path)
    return name + "/" if path.is_dir() and not path.is_symlink() else name


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = 0
    for archive in args.archives:
        try:
            result = unpack(archive, Path.cwd(), args.keep_junk)
        except (OSError, UnsupportedArchive, UnsafeArchive) as e:
            print(f"tidyx: {archive}: {e}", file=sys.stderr)
            status = 1
            continue
        note = f" ({result.junk} junk entries dropped)" if result.junk else ""
        print(f"{archive} -> {_shown(result.path)}{note}")
        for skipped in result.skipped:
            print(f"  skipped {skipped}", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())

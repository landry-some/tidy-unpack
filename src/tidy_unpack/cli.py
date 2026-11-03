"""Command-line entry point for tidyx."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .archive import UnsupportedArchive
from .extract import UnsafeArchive, plan, unpack
from .layout import Layout


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
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="show where each archive would go and what's in it, write nothing",
    )
    return parser


def _shown(path: Path) -> str:
    name = os.path.relpath(path)
    return name + "/" if path.is_dir() and not path.is_symlink() else name


def show_plan(archive: Path, target: Path, layout: Layout, junk: int) -> None:
    root = os.path.relpath(target)
    note = f", {junk} junk entries would be dropped" if junk else ""
    if layout.is_single_file:
        print(f"{archive} -> {root} (dry run{note})")
        return
    print(f"{archive} -> {root}/ (dry run{note})")
    for entry, rel in layout.members:
        line = f"  {root}/{rel}"
        if entry.kind == "dir":
            line += "/"
        elif entry.kind == "symlink":
            line += f" -> {entry.target}"
        elif entry.kind == "other":
            line += " (special file, would be skipped)"
        print(line)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = 0
    for archive in args.archives:
        try:
            if args.dry_run:
                show_plan(archive, *plan(archive, Path.cwd(), args.keep_junk))
                continue
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

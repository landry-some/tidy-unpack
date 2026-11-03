"""Decide where each archive entry goes so the result is one clean item."""

from __future__ import annotations

from dataclasses import dataclass

from .archive import Entry


@dataclass(frozen=True)
class Layout:
    """Where an archive's entries end up.

    ``root`` is the name of the single item created in the destination.
    ``members`` pairs each entry with its path relative to ``root``; an empty
    path means the entry *is* the root (a lone file).
    """

    root: str
    members: list[tuple[Entry, str]]

    @property
    def is_single_file(self) -> bool:
        return len(self.members) == 1 and self.members[0][1] == ""


def plan_layout(entries: list[Entry], stem: str) -> Layout:
    """Normalize ``entries`` into one output item.

    - One top-level folder holding everything: its contents go into ``stem``/.
    - A lone top-level file: it is written as-is under its own name.
    - Anything else (loose files, several folders): wrapped in ``stem``/.
    """
    if len(entries) == 1 and entries[0].kind == "file" and "/" not in entries[0].name:
        return Layout(entries[0].name, [(entries[0], "")])

    tops = {e.name.split("/", 1)[0] for e in entries}
    if len(tops) == 1:
        top = tops.pop()
        # It's a folder if there's a dir entry for it or anything beneath it.
        if all(e.kind == "dir" for e in entries if e.name == top):
            members = [
                (e, e.name[len(top) + 1 :]) for e in entries if e.name != top
            ]
            return Layout(stem, members)

    return Layout(stem, [(e, e.name) for e in entries])

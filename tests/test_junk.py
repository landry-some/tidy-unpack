import pytest

from tidy_unpack.archive import Entry
from tidy_unpack.junk import drop_junk, is_junk


@pytest.mark.parametrize(
    "name",
    ["__MACOSX", "__MACOSX/p/._a.txt", "p/.DS_Store", "Thumbs.db", "p/sub/desktop.ini", "p/._a.txt"],
)
def test_junk(name):
    assert is_junk(name)


@pytest.mark.parametrize("name", ["p/a.txt", ".gitignore", "p/_MACOSX", "p/.DS_Store.txt", "p/.env"])
def test_not_junk(name):
    assert not is_junk(name)


def test_drop_junk_counts():
    entries = [Entry("p/a", "file"), Entry("__MACOSX", "dir"), Entry("p/.DS_Store", "file")]
    assert drop_junk(entries) == ([Entry("p/a", "file")], 2)

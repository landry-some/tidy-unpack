from tidy_unpack.archive import Entry
from tidy_unpack.layout import plan_layout


def f(name):
    return Entry(name, "file")


def d(name):
    return Entry(name, "dir")


def rels(layout):
    return [rel for _, rel in layout.members]


def test_single_top_folder_is_collapsed():
    layout = plan_layout([d("app-1.2"), f("app-1.2/README"), f("app-1.2/src/main.c")], "app")
    assert layout.root == "app"
    assert rels(layout) == ["README", "src/main.c"]


def test_single_top_folder_without_dir_entry():
    # Many zips only list files; the folder is implied by the paths.
    layout = plan_layout([f("p/a"), f("p/b")], "p-main")
    assert layout.root == "p-main"
    assert rels(layout) == ["a", "b"]


def test_loose_files_are_wrapped():
    layout = plan_layout([f("a.txt"), f("b.txt"), d("img"), f("img/x.png")], "bomb")
    assert layout.root == "bomb"
    assert rels(layout) == ["a.txt", "b.txt", "img", "img/x.png"]


def test_lone_file_keeps_its_name():
    layout = plan_layout([f("report.pdf")], "download")
    assert layout.root == "report.pdf"
    assert layout.is_single_file


def test_lone_file_inside_folder_is_not_single_file():
    layout = plan_layout([f("docs/report.pdf")], "docs")
    assert rels(layout) == ["report.pdf"]
    assert not layout.is_single_file


def test_top_name_that_is_a_file_is_wrapped():
    # "x" is a file here, so there's no folder to collapse.
    layout = plan_layout([f("x"), Entry("x", "symlink", "y")], "s")
    assert rels(layout) == ["x", "x"]


def test_empty_archive():
    layout = plan_layout([], "empty")
    assert layout.root == "empty"
    assert layout.members == []

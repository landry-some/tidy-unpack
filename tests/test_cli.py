from tidy_unpack.cli import main


def test_unpacks_into_cwd(tmp_path, monkeypatch, capsys, zip_factory):
    arc = zip_factory("photos.zip", {"a.jpg": b"1", "b.jpg": b"2"})
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    assert main([str(arc)]) == 0
    assert (work / "photos" / "a.jpg").exists()
    assert capsys.readouterr().out.endswith("-> photos/\n")


def test_bad_archive_reports_and_continues(tmp_path, monkeypatch, capsys, zip_factory):
    bad = tmp_path / "bad.zip"
    bad.write_text("not an archive")
    good = zip_factory("good.zip", {"g/x": b"1"})
    monkeypatch.chdir(tmp_path)
    assert main([str(bad), str(good)]) == 1
    captured = capsys.readouterr()
    assert "bad.zip" in captured.err
    assert (tmp_path / "good" / "x").exists()


def test_reports_dropped_junk(tmp_path, monkeypatch, capsys, zip_factory):
    arc = zip_factory("m.zip", {"m/a": b"1", "m/.DS_Store": b""})
    monkeypatch.chdir(tmp_path)
    assert main([str(arc)]) == 0
    assert "(1 junk entries dropped)" in capsys.readouterr().out
    assert main(["--keep-junk", str(arc)]) == 0
    assert (tmp_path / "m-2" / ".DS_Store").exists()

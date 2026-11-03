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


def test_dry_run_writes_nothing(tmp_path, monkeypatch, capsys, tar_factory):
    arc = tar_factory(
        "app-1.0.tar.gz",
        {"app-1.0/": b"", "app-1.0/bin/": b"", "app-1.0/bin/run": b"x", "app-1.0/.DS_Store": b""},
        symlinks={"app-1.0/run": "bin/run"},
    )
    work = tmp_path / "work"
    work.mkdir()
    (work / "app-1.0").mkdir()
    monkeypatch.chdir(work)
    assert main(["-n", str(arc)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].endswith("-> app-1.0-2/ (dry run, 1 junk entries would be dropped)")
    assert out[1:] == ["  app-1.0-2/bin/", "  app-1.0-2/bin/run", "  app-1.0-2/run -> bin/run"]
    assert sorted(p.name for p in work.iterdir()) == ["app-1.0"]


def test_dry_run_single_file(tmp_path, monkeypatch, capsys, zip_factory):
    arc = zip_factory("dl.zip", {"report.pdf": b"%PDF"})
    monkeypatch.chdir(tmp_path)
    assert main(["--dry-run", str(arc)]) == 0
    assert capsys.readouterr().out.endswith("-> report.pdf (dry run)\n")
    assert not (tmp_path / "report.pdf").exists()


def test_dry_run_still_rejects_unsafe(tmp_path, monkeypatch, capsys, tar_factory):
    arc = tar_factory("evil.tar", {"../x": b"1"}, mode="w")
    monkeypatch.chdir(tmp_path)
    assert main(["-n", str(arc)]) == 1
    assert "unsafe path" in capsys.readouterr().err

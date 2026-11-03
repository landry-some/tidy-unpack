# Roadmap

## v0.1

- [x] Detect the format from magic bytes: zip, tar, tar.gz/.bz2/.xz, plain .gz/.bz2/.xz
- [x] Normalize the layout: one output folder named after the archive
- [x] Safe extraction: no absolute paths, `..` or escaping links; never overwrite
- [x] Drop junk entries (`__MACOSX/`, `.DS_Store`, `Thumbs.db`, `._*`), `--keep-junk` to keep them
- [x] `--dry-run` to show the target folder and entries without writing

## After v0.1 (about 31 hours)

### Features

- [ ] `--into DIR` to choose where the output folder goes (~1 h)
- [ ] 7z and rar through `7z`/`unar` when they are on PATH, with a clear error when not (~4 h)
- [ ] zstd (`.tar.zst`, `.zst`) through the `zstd` binary or `compression.zstd` on Python 3.14 (~2 h)
- [ ] `--nested` to unpack archives found inside the archive, one level deep (~2.5 h)
- [ ] Password prompt for encrypted zip entries (~1.5 h)
- [ ] `--delete` to move the archive to the trash after a successful unpack (~1.5 h)
- [ ] Progress line for large archives (~1.5 h)

### Bugs and edge cases

- [ ] Fix mojibake in zip names written in CP437 or Shift-JIS without the UTF-8 flag (~2 h)
- [ ] Keep file permissions and modification times from both zip and tar (~1.5 h)
- [ ] Handle names that clash only by case on case-insensitive filesystems (~1.5 h)
- [ ] Clean up the half-written folder when extraction fails or is interrupted (~1 h)
- [ ] Multi-part archives (`.zip.001`, `.part1.rar`) detected and reported (~1 h)

### Refactors

- [ ] Move CLI output into one reporter so `--quiet` and `--json` can share it (~2 h)
- [ ] Stream single-file decompression instead of reading whole members into memory (~1 h)

### Tests

- [ ] Property tests for path normalization with hypothesis (~2 h)
- [ ] Fixture set of real-world odd archives built by a script, not checked in as blobs (~1.5 h)
- [ ] CI on Linux, macOS and Windows with GitHub Actions (~1.5 h)

### Docs

- [ ] Man page and `--help` examples (~1 h)
- [ ] Document the normalization rules with before/after trees (~1 h)

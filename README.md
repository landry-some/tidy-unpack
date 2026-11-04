# tidy-unpack

`tidyx` unpacks an archive into exactly one folder named after it, whatever is inside.
If the archive holds a single top-level folder, that folder becomes the output. If it
spills loose files, they get wrapped in one. Either way you never end up with
`foo/foo-1.2/` nesting or forty files dumped into your current directory.

It's for anyone who downloads archives often and doesn't want to remember whether
this one needs `unzip`, `tar xzf` or `tar xJf`, or check first what the archive will do
to the current folder.

Built with Python 3.11+ and the standard library only. Tests use pytest.

## Install

```bash
git clone https://github.com/landry-some/tidy-unpack.git
cd tidy-unpack
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

## Run

```bash
tidyx release-1.2.tar.gz         # -> ./release-1.2/
tidyx photos.zip                 # -> ./photos/
tidyx --dry-run photos.zip       # show where it would go and what's inside (-n)
tidyx --keep-junk photos.zip     # keep __MACOSX/, .DS_Store and friends
tidyx --into ~/src app.tar.gz    # -> ~/src/app/ (DIR must already exist)
```

`tidyx` writes into the current directory, or into `--into DIR`, and takes several
archives at once. If one
fails, the rest are still unpacked and the exit code is 1.

## What it does to an archive

The format comes from the file's contents, not its name, so a `.zip` that is really a
`.tar.gz` still works. Supported: zip, tar, tar.gz, tar.bz2, tar.xz, and single files
compressed with gzip, bzip2 or xz.

The output is always one new item named after the archive, without its extension:

| Archive contains | Result |
|---|---|
| one top-level folder (`app-1.2/...`) | its contents go into `app-1.2/` (named after the archive) |
| loose files or several folders | they are wrapped in one folder named after the archive |
| a single file (`report.pdf`), or a plain `.gz`/`.bz2`/`.xz` | just that file, under its own name |

Nothing is ever overwritten. If the name is taken, the output becomes `name-2`,
`name-3` and so on (`report-2.pdf` for files).

macOS and Windows junk is dropped before the layout is decided, so a `__MACOSX/`
folder doesn't stop a zip from collapsing: `__MACOSX/`, `.DS_Store`, `Thumbs.db`,
`desktop.ini` and `._*` files. Pass `--keep-junk` to keep them.

### Safety

The whole archive is refused, before anything is written, if any entry:

- has an absolute path (`/etc/...`, `C:/...`) or a `..` component, or
- is a symlink whose target is absolute or would point outside the output folder.

Symlinks are created last, so no file is ever written through a link from the
archive. Devices and fifos are skipped with a message. If unpacking fails halfway, or
you press Ctrl-C, the half-written output is removed again. `--dry-run` runs the same
checks, so you can see whether an archive would be refused.

Not supported yet: 7z, rar, zstd, encrypted zips, and keeping file permissions and
modification times. These are in [ROADMAP.md](ROADMAP.md).

## Test

```bash
pytest
```

## License

MIT, see [LICENSE](LICENSE).

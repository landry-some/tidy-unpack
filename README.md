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
```

## Test

```bash
pytest
```

## License

MIT, see [LICENSE](LICENSE).

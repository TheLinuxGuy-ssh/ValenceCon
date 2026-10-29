# Contributing

Thank you for helping improve ValenceCon. Bug reports, documentation updates, and focused code changes are welcome.

## Before opening a pull request

1. Search existing issues and pull requests for related work.
2. Open an issue for substantial changes so the approach can be discussed first.
3. Keep changes focused and preserve compatibility with Kodi's Python add-on environment.
4. Do not include API keys, private server addresses, personal library data, or unredacted Kodi logs.

## Local checks

Use Python 3.12 for the same checks run in CI:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
python3 build.py --version py3
```

The build writes `dist/plugin.video.valencecon+py3.zip`. Do not commit the generated ZIP; tagged releases publish it as a GitHub Release asset.

## Pull requests

- Explain the user-visible change and the reason for it.
- Include the checks you ran and their results.
- Add or update an offline regression test when changing response parsing or other logic that can be tested without Kodi or a live server.
- Keep credentials and other private data out of commits.

By submitting a contribution, you agree that it is distributed under the repository's GNU General Public License, version 2.

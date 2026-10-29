<div align="center">
  <img src="icon.png" alt="ValenceCon logo" width="132" />
  <h1>ValenceCon</h1>
  <p>A Kodi add-on for browsing and playing media from a Valence server.</p>
  <p>
    <a href="https://github.com/TheLinuxGuy-ssh/ValenceCon/actions/workflows/ci.yaml"><img src="https://github.com/TheLinuxGuy-ssh/ValenceCon/actions/workflows/ci.yaml/badge.svg?branch=master" alt="CI status" /></a>
    <a href="https://github.com/TheLinuxGuy-ssh/ValenceCon/releases/latest"><img src="https://img.shields.io/github/v/release/TheLinuxGuy-ssh/ValenceCon" alt="Latest release" /></a>
    <a href="LICENSE.txt"><img src="https://img.shields.io/github/license/TheLinuxGuy-ssh/ValenceCon" alt="License" /></a>
  </p>
</div>

ValenceCon connects Kodi to a [Valence](https://www.getvalence.app/) media server. Browse supported libraries, open series and seasons, and play media from the Kodi interface.

<video src="./demo.mp4">

## Features

- Browse movie, television, anime, music, book, and live TV libraries.
- Navigate shows by series, season, and episode.
- Connect to multiple libraries and Valence profiles.
- Use library views and add-on features from compatible Kodi skins.

## Requirements

- Kodi 19 or later with Python 3 add-on support.
- A reachable Valence server and a valid API key.

## Installation

1. Open the [latest ValenceCon release](https://github.com/TheLinuxGuy-ssh/ValenceCon/releases/latest).
2. Download the `plugin.video.valencecon+py3.zip` asset.
3. In Kodi, choose **Add-ons → Install from zip file** and select the downloaded archive. If prompted, allow installation from unknown sources in Kodi settings.
4. Open ValenceCon and enter the Valence server address and API key. Select a profile if prompted.

For a specific version, choose it from the [release history](https://github.com/TheLinuxGuy-ssh/ValenceCon/releases).

## Configuration

Set the server address and API key in ValenceCon’s settings. Keep the API key private. When reporting an issue, remove API keys, private server addresses, and personal library information from logs and screenshots.

Kodi skins that support custom home menus or widgets can link directly to ValenceCon library and global-list views. The exact setup steps depend on the skin; consult its documentation for adding video add-on paths as menu entries or widgets.

## Development

Install the development dependencies and run the offline regression checks:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Build the Kodi Python 3 add-on archive locally:

```sh
python3 build.py --version py3
```

The generated archive is written to `dist/plugin.video.valencecon+py3.zip`, which is ignored by Git. Tagged releases build the archive and attach it to the corresponding GitHub Release.

## Repository layout

```text
resources/lib/       Add-on implementation
resources/language/  Kodi translations
resources/skins/     Skin integration assets
tests/               Offline regression tests
tools/               Optional Valence API diagnostic utility
.github/workflows/   Continuous integration and release automation
```

## Support and contributions

Use [GitHub Issues](https://github.com/TheLinuxGuy-ssh/ValenceCon/issues) for bug reports and feature requests. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Security reports should follow [SECURITY.md](SECURITY.md).

## License

ValenceCon is distributed under the GNU General Public License, version 2. See [LICENSE.txt](LICENSE.txt).

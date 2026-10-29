# Releasing ValenceCon

1. Update `version` and `changelog` in `release.yaml` and merge the change to `master`.
2. Create an annotated tag matching that version, for example `v1.0.18`.
3. Push the tag to GitHub.

The CI workflow runs the regression suite, lint checks, and package validation before creating a GitHub Release. It attaches the installable `plugin.video.valencecon+py3.zip` archive and generates release notes from the repository history. Release archives are not committed to the source tree.

The release workflow uses the repository-provided `GITHUB_TOKEN`; it does not require personal access tokens or deployment credentials.

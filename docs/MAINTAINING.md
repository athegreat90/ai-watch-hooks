# Maintaining

## Releases

A successful code-changing push to main produces one new release. Reruns reuse its version. Documentation-only changes do not need a new version. See [GitHub Releases](https://github.com/athegreat90/ai-watch-hooks/releases).

### Choosing the version

The tag is the next patch after the highest stable tag, unless the newest `## [X.Y.Z]` heading of `CHANGELOG.md` is higher: then that version is used. To ship a minor or major release, add its heading to the changelog in the pull request. A heading that is not higher than the next patch changes nothing. See `choose_tag` in `release/automatic.py`.

### Release assets

`release/assets.sh` builds `ai-watch-hooks-<tag>.zip`, `install.sh`, `install.ps1` and `SHA256SUMS` into `dist/`. The archive is reproducible (fixed timestamps, stable order). `automatic.py publish` creates the release with these files; a rerun only uploads the ones that are missing and never replaces an existing asset.

### Testing the installers

`python -m unittest discover -s tests -v` builds the assets locally and runs `install.sh` and `install.ps1` against them (`file://` release, isolated home, local receiver). Bash is required; PowerShell tests run when `pwsh` or `powershell` is found, or the executable named by `AI_WATCH_TEST_POWERSHELL`. After a release, install once from the published assets on a clean machine or folder (`--dir`) before announcing it.

## Security automation

CI scans images and Python source. Daily remediation validates pinned Python image updates before opening a PR. Set repository variable SECURITY_APP_CLIENT_ID (the app's Client ID, not its numeric App ID, which is deprecated for this action) and secret SECURITY_APP_PRIVATE_KEY using a GitHub App installed on this repository with Contents, Pull requests and Issues set to Read and write (a 403 on push or on updating the issue means the installation has not accepted those permissions). Require passing checks and human review on main. Review findings without a patch in the daily tracking issue.

## Notes

`MEMORY.md` records maintainer decisions (not user documentation).

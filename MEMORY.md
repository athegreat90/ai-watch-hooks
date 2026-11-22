# Project memory

Native hooks avoid a container startup per event. The installer and image share an exact Python pin and the CLI receives neutral output. The sender filters metadata and does not include prompts or tool arguments. Registrations use absolute paths. Native Codex and Claude registration was verified on the original Windows installation. Other native targets need CI results.

Docs decisions (2026-11-21): doc changes are folded into 1.1.0 (no new version). The two install sections are merged into one Quick start; the event-to-status table mirrors STATES in bridge/hook.py and must be updated with it. Maintainer and CI content lives in docs/MAINTAINING.md. Docker tag is a placeholder. Each repo keeps its own docs with no cross-repo files. Always record decisions here.

Trivy 0.76.2 is pinned by multi-platform image digest. The Zsh scripts resolve the repo from the script location and support overriding the interpreter with AI_WATCH_PYTHON.

HTTPS origin decision (2026-11-22, v1.1.1): `url` may be an https origin (any host name). It uses the default SSL context, so the certificate and host name are verified, with a 2 s timeout for the handshake. Plain http still requires a private IPv4 or loopback, with the 0.5 s timeout. Version 1.1.1 comes from the release automation (patch tag), not a version file.

Base image decision (2026-11-22, v1.1.2): issue #9 listed only HIGH/CRITICAL Debian bookworm CVEs without a published fix, so CI stayed green (check_findings.py fails only when a fix exists). The base moved to slim-trixie to test whether Debian 13 has fewer unfixed findings; keep it only if the CI Trivy scan is clearly better, otherwise revert and leave #9 as a tracking issue. The variant lives in security/refresh_base.py (VARIANT). The daily report is deduplicated with sort -u.

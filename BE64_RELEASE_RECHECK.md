# Remaining release dependencies — 14 October 2026

Read-only recheck of one problem: whether a released dependency update resolves the four recorded Chroma advisories. Five primary pages reviewed; no cloning, installation, external code execution or private search text. The local lock remains chromadb 1.5.9; the complete local audit recorded four findings with no fix versions.

[PyPI](https://pypi.org/project/chromadb/) still lists 1.5.9, released 5 May 2026, as the latest release. Its declared license is Apache 2.0. The four OSV records still list 1.5.9 as affected and provide no fixed-release event:

| Finding | Primary record |
|---|---|
| PYSEC-2026-311 / CVE-2026-45829 | [OSV](https://osv.dev/vulnerability/PYSEC-2026-311) |
| PYSEC-2026-3813 / CVE-2026-45830 | [OSV](https://osv.dev/vulnerability/PYSEC-2026-3813) |
| PYSEC-2026-3814 / CVE-2026-45833 | [OSV](https://osv.dev/vulnerability/PYSEC-2026-3814) |
| PYSEC-2026-3815 / CVE-2026-45831 | [OSV](https://osv.dev/vulnerability/PYSEC-2026-3815) |

No supported fixed release was identified in these sources. Verdict: retain the release finding; do not claim a clean scan or replace a reproducible dependency with an unreviewed source snapshot. No dependencies added. Upstream repository latest commit, issue responsiveness and future release date were not assessed and remain unknown. This recheck is not an exposure assessment of every possible deployment.

The concrete shared-CI proposal remains [docs/ci/security.yml](docs/ci/security.yml). As recorded in [BE53](BE53_SPRINT6_AUDIT.md), automatic approval review rejected changing persistent shared CI without specific authorization because it changes test/security coverage; a workflow-authorized credential is also required. The active workflow is unchanged. Ordinary local source fixes and verification have proceeded independently; no new remote CI, deployment or merge clearance is claimed.

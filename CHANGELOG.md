# Changelog

Package changelogs are the source of truth. This monorepo versions each
shippable package independently (package-scoped SemVer tags).

| Package | Changelog |
|---------|-----------|
| `rime-ingest` | [`packages/rime-ingest/CHANGELOG.md`](packages/rime-ingest/CHANGELOG.md) |
| `rime-client` | [`packages/rime-client/CHANGELOG.md`](packages/rime-client/CHANGELOG.md) |

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Legacy shared git tags (`v0.3` … `v0.8.2`) have been retired in favour of
`rime-ingest-vX.Y.Z` and `rime-client-vX.Y.Z`. Image tags use the SemVer
without a leading `v` (`:X.Y.Z`); container env vars carry the same version.

# Changelog

All notable changes to **rime-client** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Git tags: `rime-client-vX.Y.Z` → image `ghcr.io/<owner>/rime-client:X.Y.Z`.

## [Unreleased]

## [0.1.0]

### Added

- Standalone nginx service on port 8081, replacing the Tomcat webapp mount in
  the frost container. The client lives in `packages/rime-client/src/` and is a
  generic SensorThings API client with no build-time dependency on FROST or any
  other STA implementation; it runs on its own with no server present.
  - Serves static files only; no reverse proxy and no upstream. The browser
    talks to the STA server directly, so that server must send CORS headers.
  - Deployment default endpoint via optional `STA_ENDPOINT` and `STA_VERSION`,
    rendered into `js/runtime-config.js` at container start by nginx envsubst.
    With neither set the page loads blank and asks for a server URL.
  - STA endpoint can also be set per-session from the endpoint switcher, or
    deep-linked with `?sta=<url>&version=<v1.0|v1.1|v2.0>`.
  - If a configured server does not answer on load, the connect prompt opens
    explaining why instead of a dead error screen. Servers the user picks
    themselves still report failures directly.
  - Static files served `Cache-Control: no-cache` so a redeploy is picked up on
    the next load (filenames are unversioned).
  - Unknown paths return `404` instead of falling back to `index.html`.

### Fixed

- Endpoint chosen in the switcher is persisted to `localStorage` across reload.
  Credentials remain in memory for the session only.

### Changed

- Adopt package-scoped SemVer tags (`rime-client-vX.Y.Z`); git tag is the
  release source of truth. CI stamps `RIME_CLIENT_VERSION` into the image
  (legacy shared monorepo `v*` tags retired).

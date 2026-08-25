# Changelog

All notable changes to **rime-client** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Git tags: `rime-client-vX.Y.Z` → image `ghcr.io/<owner>/rime-client:X.Y.Z`.

## [Unreleased]

### Added

- **OData query builder** (`query.html`) — a read-only page for composing and
  running STA queries against the configured server. Pick an entity type, add
  filter conditions, and set `$select` / `$expand` / `$orderby` / `$top` /
  `$skip` / `$count`; the request URL is shown live, copyable, and valid to paste
  into `curl`. Responses are pretty-printed with row count, total and timing, and
  `@iot.nextLink` is followed with a "Next page" control.
  - **Version-aware operators.** The filter operator list comes from the selected
    STA version rather than being hard-coded: v1.1 offers `substringof`, v2.0
    offers `contains` (OData 4.01 dropped `substringof`). Measured against FROST
    2.6 on v1.1: `substringof('Room', name)` → 200, `contains(name, 'Room')` →
    400. Switching version resets any condition whose operator does not exist in
    the newly selected version. New module `js/odata.js` owns this vocabulary,
    following the pattern `js/frost-fields.js` uses for annotation field names.
  - Shares the endpoint with the map page through the same `localStorage` keys,
    so switching server on either page carries over.
  - Server quick-pick dropdown, and a free-text field for anything else.
  - Nothing on this page writes to the STA server.

### Changed

- **Known STA servers come from one list.** `STA_KNOWN_SERVERS` in `js/config.js`
  now feeds both the map's endpoint quick-picks and the query builder's server
  dropdown, so the two cannot drift apart.

### Fixed

- **Command bar overflowed at common desktop widths.** `.status-legend` was
  `flex-shrink: 0` at ~730px wide, forcing ~1430px of content into a 1250px bar:
  at 1280px the endpoint switcher and both doc links were pushed outside the
  viewport entirely. The legend now shrinks and scrolls, command-bar children
  get `min-width: 0` so they can shrink at all, and the chip labels drop at
  1500px rather than 1100px (they were hidden too late to help). Verified with no
  overflow at 1600 / 1280 / 1150 / 960 / 600 / 375 px.
- **Query builder bar overlapped the page on narrow viewports** — it reused the
  `.command-bar` class, which is absolutely positioned with a fixed height for
  the map stage. It is now styled standalone and wraps cleanly.

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

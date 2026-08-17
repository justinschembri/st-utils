# Changelog

All notable changes to **rime-ingest** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Git tags: `rime-ingest-vX.Y.Z` → image `ghcr.io/<owner>/rime-ingest:X.Y.Z`.

## [Unreleased]

## [0.10.0]

### Added

- Standalone `rime-ingest` run CLI for host deploys: point at application,
  sensor, and credential paths (or a dotenv file) and start ingest in-process
  without Docker.
- OTT Hydras 3 provider (`ott-hydras3`) and `ott.rls` ingest path for sectioned
  `.MIS` snapshots, including water-level parsing/normalization and an RLS
  probe sensor-config template.
- `DiffDirectoryWatcher` for rewritten snapshot files, alongside EOF watchers
  for append-only logs.

### Changed

- Split filesystem poll watchers into EOF and Diff variants
  (`FileWatcher` / `DirectoryWatcher` → `EOFFileWatcher` / `EOFDirectoryWatcher`).
- GHCR image tags no longer include a leading `v`. Git tags remain
  `rime-ingest-vX.Y.Z`; images are `ghcr.io/<owner>/rime-ingest:X.Y.Z`.
- Improved timezone resolution on Windows.

### Fixed

- Clear pending FROST flush after upload failures so a failed flush does not
  block later buffered observations for the same sensor.

## [0.8.2]

### Added

- Generic SeedLink provider.

### Changed

- Canonical Datastream names via `CanonicalDatastreams`, restricting allowable
  names for consistency between the application and FROST entities.
- Dockerfile multi-stage build (`ghcr.io/astral-sh/uv:python3.13-bookworm`
  builder, `python:3.13-slim` runtime).
- Adopt package-scoped SemVer tags (`rime-ingest-vX.Y.Z`); git tag is the
  release source of truth. CI stamps `RIME_INGEST_VERSION` into the image.
  `pyproject.toml` version is a non-release placeholder (`0.0.0`).

### Fixed

- CLI indentation error in `cli/commands.py` that prevented `rime setup` from
  running.

---

## Pre-package-tag history (shared monorepo `v*` tags)

These entries describe work published under the old repo-wide tags
(`v0.3` … `v0.8.2`). They are retained for context only.

### [v0.6.0]

#### Changed

- **Decapsulation package rename (BREAKING)** — `transformers/envelopes` is now
  `transformers/decapsulators`. Imports and docs have been updated accordingly.
- **Milesight normalizer naming (BREAKING)** — renamed
  `MilesightAm103lPayload` / `MilesightAm308lPayload` to
  `MilesightAm103lNormalizer` / `MilesightAm308lNormalizer`.
- **Application config provider key (BREAKING)** — application config now uses
  `provider` ids instead of `connection_class` names. Runtime and CLI now
  resolve providers through `providers/registry.py` (`PROVIDER_REGISTRY`), with
  fail-fast validation for missing/unknown providers.
- **HTTP config field alignment** — CLI-generated HTTP application config now
  writes `request_interval` to match transport/provider constructor parameters.

#### Added

- **Generic HTTP provider** — added `GenericHTTPProvider` and registry id
  `generic-http` for config-driven JSON HTTP polling and field-mapped
  decapsulation (`url`, method/headers/params, response item field, sensor id
  field, payload field, optional timestamp fields).
- **Contributor checklist** — added `CONTRIBUTING.md` with a decision-driven
  checklist for adding transports, providers, decapsulators, and sensor model
  mappings.

#### Documentation

- Updated root and `src/rime` READMEs with current ingest lifecycle diagrams and
  pipeline tables.
- Refreshed provider and transformer docs to match decapsulator naming,
  provider-id config, and current ingest-stage responsibilities.
- Rebuilt CLI tape outputs and documented tape generation flow.

### [v0.5.0]

#### Fixed

- **Observation POST URLs** — `find_datastream_observations_url` now returns the
  Datastream entity URL (``@iot.selfLink`` or ``.../Datastreams(id)``), not the
  ``Observations`` navigation link. ``make_frost_entity`` appends ``/Observations``
  once, fixing doubled paths like ``.../Observations/Observations`` that caused
  HTTP 404 from FROST.

#### Changed

- **Project rename (BREAKING)** — Distribution, CLI command, and Python import
  package are **rime** (`import rime`, `rime` console script). Docker Compose default
  project **`rime-production`** (was `st-utils-production`); Tomcat dashboard is
  served at **`/rime`** under the webapps root (was `/st-utils`). Persistent
  Postgres volume detection accepts both **`rime-production_postgis_volume`** and
  legacy **`st-utils-production_postgis_volume`**. The OGC SensorThings model
  package is **`rime.sta`** (was **`rime.sensor_things`**).
- **Connections refactor (BREAKING)** — `connections.py` is replaced by two
  top-level packages: [`transport/`](src/rime/transport/README.md)
  for protocol-agnostic and protocol-level abstractions, and
  [`providers/`](src/rime/providers/README.md) for
  application-specific integrations. The base class
  `SensorApplicationConnection` becomes `SensorTransport`; protocol abstracts
  `HTTPSensorApplicationConnection` / `MQTTSensorApplicationConnection`
  become `HTTPTransport` / `MQTTTransport`; concrete providers
  `NetatmoConnection` / `TTSConnection` become `NetatmoProvider` /
  `TTSProvider`. Lifecycle methods are renamed
  `start_pull_transform_push_thread` → `start`,
  `stop_pull_transform_push_thread` → `stop`,
  `restart_pull_transform_push_thread` → `restart`, and a new `is_alive`
  property replaces external `_thread.is_alive()` checks. The MQTT
  `_pull_data` method (which actually connects + subscribes) is renamed to
  `_connect`.
- **Authentication moves into providers** — the `authentication_type` /
  `_authentication_file` fields and constructor argument are removed from
  the base class. Each provider resolves its own credentials inside
  `_auth()`. Update existing `deploy/application-configs.yml`:
  - drop `authentication_type` keys (no longer read),
  - rename `connection_class: NetatmoConnection` → `NetatmoProvider`,
  - rename `connection_class: TTSConnection` → `TTSProvider`.

#### Internal

- New package layout: `transport/{base,poll/http,subscription/mqtt}.py`
  for protocol-agnostic and protocol-level abstractions, and
  `providers/{netatmo,tts}.py` for application-specific integrations.
  Each package has its own README documenting the contract.
- Provider classes now declare their CLI credential helper via
  `auth_method: ClassVar[Literal["tokens", "credentials"]]`.
- Fix broken tests.
- **FROST package refactor** — the `frost` sub-package has been restructured
  into focused, single-responsibility modules:
  - `types.py` — enums (`FrostVersions`, `FrostEndpoints`, `FrostParams`) and
    the `FrostEntityRef` dataclass.
  - `errors.py` — exception hierarchy (`FrostConnectionError`,
    `FrostRequestError`, `FrostNoResultsError`, `FrostWriterError`).
  - `bridges.py` — lookup tables between the SensorThings domain model and the
    FROST wire protocol (navigation-link keys, endpoint paths).
  - `sanitization.py` — URL/param normalisation helpers and OData clause
    builders (`sanitize_get_request`, `sanitize_root_url`, `merge_filter`,
    `merge_order_by`, `rewrite_to_internal`).
  - `get.py` — paginated entity lookups, object lookups, datastream observation
    queries, and navigation-link resolution.
  - `post.py` — raw POST, idempotent entity creation, and observation upload.
  - `helpers.py` — per-type existence checkers and the connectivity probe.
  - `writers.py` — `FrostWriter` class supporting stream and buffered JSON/CSV
    output with atomic file rename.
  - `orchestrators.py` — `initial_setup` for full sensor-config provisioning in
    dependency order.
- Added Google-style docstrings across all FROST modules.
- Added `frost/README.md` describing the package structure, data flow, and
  key design decisions.
- **Fix external requests on paginated queries** (#61) — `frost_entity_lookup_pages`
  now rewrites `@iot.nextLink` URLs to the internal root before following them,
  closing the path by which containerised deployments with a public
  `serviceRootUrl` would leak paginated GET requests outside the container
  network. Navigation links in POST paths were already handled via
  `rewrite_to_internal`; this closes the remaining gap.
- **Remove `frost_data_retrieval.py`** — legacy predecessor to the `frost/`
  package; no longer imported anywhere and superseded by `frost/get.py`.

### [v0.4.2]

#### Fixed

- **Improved restart policy** - dead threads do not cause app restarts, but connections
  to restart.

### [v0.4.1]

#### Fixed

- **Python Version** - upgraded minimum python version to 3.12 due to typing styles
  are PEP 701 compliant and therefore not compatabile with earlier versions.

### [v0.4.0]

#### Added

- **Mount points** → The directories where sensor and application configuration
  files live (`deploy/sensor_configs` and `deploy/application-configs.yml`)
  are now always mounted in `docker-compose` files.
- **Support for external configuration directories** → By specifying the
  environment variables `SENSOR_CONFIG_PATH` and `APPLICATION_CONFIG_FILE` or by
  declaring them in a `.env` file in `/deploy`, you can point to an external
  host location for configuration files. This allows users to have separate git
  worktrees for configuration.

#### Changed

- **Sensor config sourcing**: Config loading and generation use overridable
  paths; config generator reads templates and writes generated configs under the
  variable sensor config path.
- **Preflight execution**: Preflight runs at thread start instead of in
  `__init__`, so subclass attributes (e.g. MQTT `topic`) are set and failure
  prevents the connection from starting.
- **MQTT callbacks**: Improved connection and subscription logging/callbacks in
  MQTT sensor application connections.
- **Docker Compose**: Application config mount target aligned (typo fix in
  `docker-compose.app.yml`).

#### Removed

- **requirements.txt**: Removed legacy `requirements.txt` in favour of
  `pyproject.toml` / uv for dependency management.

#### Internal

- `.gitignore`: Added CSV ignore and cleanup.
- **Preflight checks** for sensor application connections. Subclasses can
  override `_preflight()` to run checks before a connection starts (e.g. TTS
  topic must include tenant ID `@ttn`). Preflight runs when starting the
  pull/transform/push thread; on failure the connection is not started and a
  warning is logged.
- **Date option handling** for FROST data retrieval (#58).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.4.2]

### Fixed

- **Improved restart policy** - dead threads do not cause app restarts, but connections
  to restart.

## [v0.4.1]

### Fixed

- **Python Version** - upgraded minimum python version to 3.12 due to typing styles
  are PEP 701 compliant and therefore not compatabile with earlier versions.

## [v0.4.0]

### Added

- **Mount points** → The directories where sensor and application configuration
  files live (`deploy/sensor_configs` and `deploy/application-configs.yml`)
  are now always mounted in `docker-compose` files.
- **Support for external configuration directories** → By specifying the
  environment variables `SENSOR_CONFIG_PATH` and `APPLICATION_CONFIG_FILE` or by
  declaring them in a `.env` file in `/deploy`, you can point to an external
  host location for configuration files. This allows users to have separate git
  worktrees for configuration.

### Changed

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

### Removed

- **requirements.txt**: Removed legacy `requirements.txt` in favour of
  `pyproject.toml` / uv for dependency management.

### Internal

- `.gitignore`: Added CSV ignore and cleanup.
- **Preflight checks** for sensor application connections. Subclasses can
  override `_preflight()` to run checks before a connection starts (e.g. TTS
  topic must include tenant ID `@ttn`). Preflight runs when starting the
  pull/transform/push thread; on failure the connection is not started and a
  warning is logged.
- **Date option handling** for FROST data retrieval (#58).

# `rime-ingest`

Ingest layer for the rime platform: polls/subscribes to upstream providers,
runs the decode → decapsulate → normalize pipeline, and uploads observations
to FROST.

This package is **self-contained**. Runtime configuration and secrets are
mounted by `deploy/` compose files — ingest does not depend on a monorepo
layout inside the container.

## Build and run

```bash
cd packages/rime-ingest
uv sync
rime setup
rime-ingest run   # start ingest on the host (or: python -m rime_ingest.main)
```

## Host deploy (`rime-ingest run`)

Use this when running ingest outside Docker (e.g. Windows). It starts the same
process as the container `CMD`, with path overrides written into the environment
before boot.

```bash
# Explicit flags (paths mirror deploy/ compose mounts)
rime-ingest run \
  --applications ./application-configs.yml \
  --sensors ./sensor_configs \
  --credentials ./secrets/credentials \
  --tokens ./secrets/tokens \
  --logs ./logs \
  --frost-endpoint http://frost-host:8080/FROST-Server \
  --frost-version v1.1

# Or load a dotenv file (CLI flags still override)
rime-ingest run --env-file C:\rime\ingest.env
```

Example `ingest.env`:

```env
APPLICATION_CONFIG_FILE=C:\rime\application-configs.yml
SENSOR_CONFIG_PATH=C:\rime\sensor_configs
RIME_CREDENTIALS_DIR=C:\rime\secrets\credentials
RIME_TOKENS_DIR=C:\rime\secrets\tokens
RIME_LOGS_DIR=C:\rime\logs
FROST_ENDPOINT=http://frost-host:8080/FROST-Server
FROST_VERSION=v1.1
```

Precedence: process environment → `--env-file` → CLI flags. Without flags or an
env file, monorepo checkouts still default to `deploy/` paths.

The older `rime` CLI (`setup`, `validate`, `generate-config`, compose
`start`/`stop`) is unchanged and separate from `rime-ingest run`.

## Docker

Built from this directory only:

```bash
docker build -t rime-ingest .
```

In production, use the compose overlays under `deploy/` at the monorepo root.
Compose mounts host paths into the container runtime directories below.

## Versioning and release

`rime-ingest` versions independently of other monorepo packages.

**Git tags are the source of truth.** Pushing `rime-ingest-vX.Y.Z` runs tests,
then builds and pushes `ghcr.io/<owner>/rime-ingest:vX.Y.Z` and stamps
`RIME_INGEST_VERSION` into the image (see Dockerfile `ARG VERSION`).

`pyproject.toml` `version` is a placeholder (`0.0.0`) for local installs — it
does not track releases (images are not published as PyPI libraries).

| Item | Value |
|------|--------|
| Changelog | [`CHANGELOG.md`](CHANGELOG.md) |
| Git tag | `rime-ingest-vX.Y.Z` |
| Image | `ghcr.io/<owner>/rime-ingest:vX.Y.Z` |
| Runtime | `RIME_INGEST_VERSION` (e.g. `0.8.2`; `dev` for local builds) |

### Cut a release

1. Update `CHANGELOG.md` (`Unreleased` → new section).
2. Commit on the branch you intend to tag (usually `main`).
3. Tag and push: `git tag rime-ingest-vX.Y.Z && git push origin rime-ingest-vX.Y.Z`.
4. CI (`.github/workflows/release-rime-ingest.yml`) tests, then builds and pushes
   the image.

### Run a pinned image

```bash
docker run --rm ghcr.io/<owner>/rime-ingest:v0.8.2
```

Local `deploy/docker-compose.base.yml` still builds from source (`VERSION=dev`).
To pin a published image, set the service `image` to the GHCR tag and drop (or
comment out) `build:` for that service.

## Runtime paths

When `CONTAINER_ENVIRONMENT=true` (set in the Dockerfile), defaults are:

| Env var | Container default | Purpose |
|---------|-------------------|---------|
| `SENSOR_CONFIG_PATH` | `/app/runtime/sensor_configs` | Sensor YAML configs |
| `APPLICATION_CONFIG_FILE` | `/app/runtime/application-configs.yml` | Application config |
| `RIME_CREDENTIALS_DIR` | `/app/runtime/secrets/credentials` | Provider credentials |
| `RIME_TOKENS_DIR` | `/app/runtime/secrets/tokens` | OAuth token files |
| `RIME_LOGS_DIR` | `/app/logs` | Log output |

When developing inside the monorepo, local defaults automatically use
`deploy/` (sensor configs, credentials, application config). No extra env vars
are needed for `rime setup` or `rime validate`.

Standalone installs (without a sibling `deploy/` directory) fall back to
`packages/rime-ingest/runtime/`.

FROST connectivity uses `FROST_ENDPOINT` or `FROST_ROOT_URL` + `FROST_VERSION`.

## Stack lifecycle (`rime start` / `rime stop`)

These commands invoke scripts in `deploy/`. From a monorepo checkout,
`deploy/` is discovered automatically. Otherwise set:

```bash
export RIME_COMPOSE_DIR=/path/to/deploy
```

Prefer running `docker compose` from `deploy/` directly in production.

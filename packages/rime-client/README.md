# rime-client

An nginx container serving the rime web client — a Leaflet map and chart viewer for any
[OGC SensorThings API](https://www.ogc.org/publications/standard/sensorthings/) server.

It serves static files and nothing else: no reverse proxy, no upstream, and no dependency
on FROST, on `rime-ingest`, or on any particular STA implementation. The browser talks to
the STA server directly; this container only hands it a URL.

## Two ways to run it

It is the **same image and the same code** in both cases. The only difference is whether
the `STA_ENDPOINT` environment variable is set.

### On its own — starts blank

```bash
docker build -t rime-client packages/rime-client
docker run --rm -p 8081:80 rime-client
```

No `STA_ENDPOINT`, so the page has no server to talk to. It loads an empty map and opens
the connect box. Nothing is fetched and nothing errors — paste in any STA server and it
works. This is the case that must never require a FROST alongside it.

### With the dev stack — connects automatically

```bash
cd deploy && ./start-dev.sh
```

Then open <http://localhost:8081>. The map is populated on load, with no prompt.

That happens because of one line in `deploy/docker-compose.base.yml`:

```yaml
rime-client:
  environment:
    - STA_ENDPOINT=${STA_ENDPOINT:-http://localhost:${FROST_BIND_PORT:-8080}/FROST-Server}
```

**This line is the only thing in the repo connecting the client to FROST.** It lives on the
`rime-client` service, not on `frost`, because environment variables are per-container and
because the value ultimately has to reach the *browser*. Delete the line and the same stack
comes up with a blank client.

You can get either behaviour from either launch method — the compose default is just a
convenience:

```bash
docker run --rm -p 8081:80 -e STA_ENDPOINT=http://localhost:8080/FROST-Server rime-client
```

> `STA_ENDPOINT` is **browser-facing**. It must be reachable from the user's machine, so
> `http://frost:8080` does *not* work even though that is the service name — your browser
> cannot resolve Docker service names.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `STA_ENDPOINT` | *(empty)* | STA base URL, **without** the version segment — `https://sta.example.org`, not `https://sta.example.org/v1.1`. Empty means start unconfigured. |
| `STA_VERSION` | `v1.1` | `v1.0`, `v1.1` or `v2.0`. |

## Which server the page uses

`STA_ENDPOINT` is only the deployment *default*. At load time the client takes the first of:

1. `?sta=<url>&version=<v1.0|v1.1|v2.0>` — shareable deep links
2. `localStorage` — the server the user last picked in the endpoint switcher
3. `window.RIME_CONFIG` — the `STA_ENDPOINT` default
4. nothing — blank page, connect box opens

There is deliberately **no fallback to the client's own origin**. rime-client may be
deployed with no STA server of its own, and guessing one produces a broken page.

The switcher in the top bar also takes HTTP basic credentials for read access. Those stay
in memory for the session and are never written to `localStorage`.

> **Testing gotcha:** rule 2 outranks the deployment default, and `localStorage` is
> per-port. If you have ever picked a server in the switcher on a given port, that choice
> wins over `STA_ENDPOINT` for *your* browser while a colleague opening it fresh sees the
> configured one. Test on an unused port, or run `localStorage.clear()` in the console.

## When the configured server does not answer

There is no service discovery — the client finds out by making the request and seeing what
happens. Which failure you get depends on **who chose the endpoint**:

| Endpoint came from | On failure |
|---|---|
| Stored or deployed config (rules 1–3) | Connect box opens: *"Could not reach … — choose a server."* |
| The user typing it into the switcher | Red **Connection Failed** error |

The reasoning: nobody typed a stored or deployed endpoint in this session, so a stale or
stopped server should get a do-over rather than a dead error screen. A server the user just
entered deserves a straight answer. In the code this is the `isInitialLoad` flag in
`app.js`, cleared by `resetAndReload()` in `js/ui.js`.

## No proxy — the browser goes direct

An earlier version of this package reverse-proxied `/FROST-Server/` to `frost:8080`. That
was removed: it made the container fail to start when no `frost` host existed, and it baked
one STA implementation into a static file server.

The consequence is that **the STA server must be browser-reachable and must send CORS
headers**. FROST does, via `http_cors_enable=true` and `http_cors_allowed_origins=*` in
`deploy/docker-compose.base.yml`.

If you later need the STA server off the public network, put a real ingress (Traefik,
Caddy, a k8s ingress) in front of both services and point `STA_ENDPOINT` at the public
path. Routing policy does not belong in the file server.

## How the endpoint reaches the browser

nginx serves files from disk and cannot read environment variables, so `STA_ENDPOINT` has
to become a file. At container start nginx's **own** entrypoint script
(`/docker-entrypoint.d/20-envsubst-on-templates.sh`) renders `runtime-config.js.template`
into `js/runtime-config.js`, which `index.html` loads before the app. There is no custom
entrypoint script; the Dockerfile just points `NGINX_ENVSUBST_OUTPUT_DIR` at the webroot.

Two things in the Dockerfile look redundant but are not:

- `ENV STA_ENDPOINT=""` / `ENV STA_VERSION="v1.1"` — `envsubst` only substitutes variables
  that exist in the environment. Without these, an unset `STA_ENDPOINT` leaves the literal
  text `${STA_ENDPOINT}` in the served JavaScript.
- `Cache-Control: no-cache` in `nginx.conf` — filenames are unversioned (`app.js`,
  `styles.css`), so browsers otherwise keep running old code after a redeploy. It still
  caches; it just revalidates, so unchanged files come back `304`.

Serving `src/` outside Docker works too — it is plain static files, no build step. The
checked-in `src/js/runtime-config.js` is the unconfigured default.

## Build

The package is self-contained, so the build context is the package directory:

```bash
docker build -t rime-client packages/rime-client
```

## Versioning and release

`rime-client` versions independently of other monorepo packages.

**Git tags are the source of truth.** Pushing `rime-client-vX.Y.Z` builds and
pushes `ghcr.io/<owner>/rime-client:X.Y.Z` and stamps `RIME_CLIENT_VERSION`
into the image (see Dockerfile `ARG VERSION`).

| Item | Value |
|------|--------|
| Changelog | [`CHANGELOG.md`](CHANGELOG.md) |
| Git tag | `rime-client-vX.Y.Z` |
| Image | `ghcr.io/<owner>/rime-client:X.Y.Z` |
| Runtime | `RIME_CLIENT_VERSION` (e.g. `0.1.0`; `dev` for local builds) |

SemVer tracks the **image contract**: major for breaking env/query/behaviour
changes, minor for features, patch for fixes. Static asset filenames stay
unversioned; `Cache-Control: no-cache` handles cache busting.

### Cut a release

1. Update `CHANGELOG.md` (`Unreleased` → new section).
2. Commit on the branch you intend to tag (usually `main`).
3. Tag and push: `git tag rime-client-vX.Y.Z && git push origin rime-client-vX.Y.Z`.
4. CI (`.github/workflows/release-rime-client.yml`) builds and pushes the image.

### Run a pinned image

```bash
docker run --rm -p 8081:80 ghcr.io/<owner>/rime-client:0.1.0
```

Local `deploy/docker-compose.base.yml` still builds from source (`VERSION=dev`).
To pin a published image, set the service `image` to the GHCR tag and drop (or
comment out) `build:` for that service.

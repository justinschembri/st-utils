# `transport`

Abstractions describing **how** sensor data moves from an upstream source
into the rime pipeline. This package is framework code: it changes
rarely, and only when adding support for a fundamentally new way of
communicating with a sensor application.

If you are integrating a new sensor application (Chirpstack, Helium,
Sigfox, ...) you almost certainly want
[`../providers/`](../providers/README.md) instead. You only need to add
something here when no existing transport fits — for example, a SeedLink
TCP stream, a CoAP poller, or a directory watcher.

## Architecture

```
transport/
├── base.py                  # SensorTransport (ABC) -- protocol-agnostic core
├── poll/                    # caller drives the rhythm; stateless requests
│   ├── http.py              # HTTPTransport (ABC)
│   └── fs.py                # EOF* append watchers; DiffDirectoryWatcher (snapshot diff)
└── subscription/            # source pushes to caller; persistent connection
    ├── mqtt.py              # MQTTTransport (ABC)
    └── seedlink.py          # SeedLinkTransport (ABC, ObsPy SeedLink TCP)
```

![](../../../docs/imgs/transport-class-diagram.drawio.svg)

The package is organised in two layers:

1. **Interaction model** (`poll/`, `subscription/`) — *who drives the data
   flow*. Polling means the caller asks on a schedule; subscription means
   the source pushes when something happens. These are the most stable
   architectural divisions because they are about control flow, not wire
   format.
2. **Protocol implementation** (`http.py`, `mqtt.py`, `seedlink.py`, ...) — the
   concrete abstract class that handles a specific wire protocol within an
   interaction model. Filesystem polling lives in `poll/fs.py`.

## Ingest pipeline (transport → FROST)

The pipeline runs in two stages inside `SensorTransport._process_wire_message`.

### Provider tier  *(transport / provider level)*

| Step | Hook | Default | Responsibility |
|------|------|---------|----------------|
| 1 | `_run` | — | Receive one wire message from upstream; call `_process_wire_message`. |
| 2 | `_decode_wire` | identity | Convert raw bytes to a decoded form (e.g. base64 → bytes, bytes → UTF-8). |
| 3 | `_deserialize_wire` | identity (`json.loads` on MQTT) | Parse the decoded form into a Python object (JSON, CBOR, Protobuf, ...). |
| 4 | `_decapsulate_wire` | **abstract** | Strip the provider envelope; return a `DecapsulatedMessage` whose `identified_payloads` list contains one `IdentifiedPayload` per logical sensor. |

Steps 2 and 3 default to the identity on `SensorTransport`. Transport
subclasses override where needed: `MQTTTransport` overrides
`_deserialize_wire` with `json.loads`; SeedLink and HTTP leave both as
identity because their underlying libraries (ObsPy, lnetatmo) already return
Python objects.

### Model tier  *(per `IdentifiedPayload` in `identified_payloads`, keyed by sensor model)*

| Step | Component | Source | Responsibility |
|------|-----------|--------|----------------|
| 5 | `parser.parse(identified, envelope)` | `INGEST_COMPONENT_MAP[model]` | Assemble `ObservationRecord`: `sensor_uuid`, observation-only `observations` dict, resolved timestamps. |
| 6 | `normalizer.from_record` + `to_stObservations` | `INGEST_COMPONENT_MAP[model]` | Vendor fields → SensorThings Observation tuples. |
| 7 | `frost_observation_upload` | `SensorTransport` | Push each observation to FROST. |

## What the top level `SensorTransport` owns

- Threading lifecycle: `start()`, `stop()`, `restart()`, `is_alive`.
- The shared processing pipeline: `_process_wire_message` orchestrates both
  tiers above, calling the application-tier hooks then the model-tier
  components, regardless of which transport is in use.
- Exception classification: `_exception_handler` returns `0` for
  transient errors and `1` for real failures, with `max_retries`
  governing when the transport gives up.
- Construction from YAML: `from_config` introspects the constructor
  signature and forwards matching keys; subclasses rarely need to
  override.

What it intentionally does **not** own and are specified in `providers`:

- **Authentication.** Credential storage and resolution differ enough between
  providers (OAuth, API keys, TLS certificates, no auth) that forcing a shape
  here would be the wrong abstraction. Providers handle their own auth.
- **Sensor-specific decoding.** `SensorTransport._process_wire_message` only calls
  the `INGEST_MAP`, which maps a `SupportedSensor` to a suite of
  `IngestModelComponents`.

## Adding a new transport

When adding a new transport you are answering two questions:

1. *Is this poll or subscription?* — pick the right subdirectory.
2. *What is the protocol's lifecycle?* — implement `_run` (and helpers
   such as `_connect`, `_pull_data`) to drive `_process_wire_message`. Override
   `_decode_wire` and/or `_deserialize_wire` if the wire format requires
   it; leave them as identity if the underlying library already returns a
   Python object.

Then export from `transport/__init__.py` and document the contract in the
module docstring.

## Adding a new interaction model

This is rarer. You would only do this if a new model fundamentally
differs from poll-and-subscribe — for example, a one-shot batch
ingestion that runs once and exits. Create a new subdirectory under
`transport/` with its own protocol files inside.

## See also

- [`../providers/`](../providers/README.md) — concrete integrations with
  specific applications, built on top of these transports.
- [`../transformers/`](../transformers/) — payload normalisation and
  conversion to SensorThings observations.
- [`../monitor.py`](../monitor.py) — health monitoring; transports report
  payload counts and the monitor restarts dead threads.

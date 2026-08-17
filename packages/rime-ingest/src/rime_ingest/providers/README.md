# `providers`

Concrete integrations with specific upstream sensor applications:
Netatmo, TheThingsStack, Chirpstack, ... A provider answers **where**
data comes from, building on a transport from
[`../transport/`](../transport/README.md) which answers **how** it gets
here.

This is the active growth area of the project. Adding a new provider is
the most common kind of contribution and should be as painless as
possible.

## Current providers

| Provider          | Transport                          | Auth            | Notes                                            |
| ----------------- | ---------------------------------- | --------------- | ------------------------------------------------ |
| `GenericHTTPProvider` | `HTTPTransport` (poll)         | Config headers  | Generic JSON HTTP pull + field-mapped decapsulation. |
| `NetatmoProvider` | `HTTPTransport` (poll)             | OAuth tokens    | Polls `WeatherStationData.rawData` via lnetatmo. |
| `TTSProvider`     | `MQTTTransport` (subscription)     | API key         | Subscribes to `v3/<app>/devices/+/up` topics.    |
| `EltekGPRSServerProvider` | `EOFFileWatcher` (poll)    | none            | Watches CSV written by Eltek Gateway GPRS Server; channel → Sensor UUIDs. |
| `OTTHydra3Provider` | `DiffDirectoryWatcher` (poll) | none         | Sectioned `.MIS` snapshots under dated dirs; sensor id → Sensor UUIDs. |

## What a provider owns

A provider is the smallest piece of code needed to integrate a new
upstream application. It declares:

1. **The transport it uses.** By inheriting from `HTTPTransport` or
   `MQTTTransport` (or any future transport), it picks up the threading
   model, payload pipeline, and exception handling for free.
2. **Provider decapsulation.** Implement `_decapsulate_wire(self, wire_message)`
   to strip the provider envelope and return a single `DecapsulatedMessage`
   whose `identified_payloads` list contains one `IdentifiedPayload` per logical
   sensor in the wire message.  Model-specific parsing and transformation are
   handled centrally by `SensorTransport` using
   [`../transformers/ingest_registry.py`](../transformers/ingest_registry.py).
3. **Authentication.** Provider-local. Resolve credentials from
   wherever they are stored (token file, credentials JSON, env vars,
   TLS certs) inside `_auth()`.
4. **The data fetch.**
   - For HTTP: implement `_pull_data` to return a single payload.
   - For MQTT: implement `_auth` to configure the broker client; the
     transport's `_connect` handles subscription.
5. **Optional preflight checks.** Override `_preflight()` to return
   `False` and abort startup if the provider config is invalid (e.g. a
   topic missing a tenant ID).
6. **A CLI hint** for credential setup:
   ```python
   auth_method: ClassVar[Literal["tokens", "credentials"]] = "tokens"
   ```
   Used by `rime setup` to invoke the right credential helper. Defaults
   to `"credentials"` if not set.

## Adding a new provider

For something that just speaks an existing transport (Chirpstack,
Helium Console, AWS IoT Core, ...) the steps are:

1. Add `providers/<name>.py` with a class extending the appropriate
   transport ABC.
2. Implement `_decapsulate_wire`.
3. Implement `_auth` and (for HTTP) `_pull_data`.
4. Set `auth_method`.
5. Re-export from `providers/__init__.py`.
6. Add an entry to the table above.

Skeleton (MQTT-based provider):

```python
# providers/chirpstack.py
import json
import logging
from typing import Any, ClassVar, Literal

from ..paths import CREDENTIALS_DIR
from ..transformers.decapsulators import ChirpstackDecapsulator  # hypothetical
from ..transformers.messages import DecapsulatedMessage
from ..transport import MQTTTransport

event_logger = logging.getLogger("events")


class ChirpstackProvider(MQTTTransport):
    """Chirpstack provider over MQTT."""

    auth_method: ClassVar[Literal["tokens", "credentials"]] = "credentials"

    def _decapsulate_wire(self, wire_message: Any) -> DecapsulatedMessage:
        return ChirpstackDecapsulator.decapsulate(wire_message)

    @property
    def _credentials_file(self):
        return CREDENTIALS_DIR / "application_credentials.json"

    def _auth(self) -> None:
        if not self._credentials_file.exists():
            raise FileNotFoundError(...)
        with open(self._credentials_file) as f:
            creds = json.load(f).get(self.app_name, {})
        self._mqtt_client.username_pw_set(creds["username"], creds["password"])
        self._mqtt_client.tls_set()
```

For something that needs a brand-new transport (e.g. SeedLink, an
FTP-drop watcher), build the transport first under
[`../transport/`](../transport/README.md), then build the provider on
top.

## Configuration

Providers are wired up via `deploy/application-configs.yml`:

```yaml
applications:
  generic-weather:
    provider: generic-http
    url: https://api.example.com/weather
    method: GET
    request_interval: 300
    response_items_field: data
    sensor_id_field: station_id
    payload_field: readings
    phenomenon_timestamp_field: observed_at
  multicare-acerra@ttn:
    provider: tts
    host: eu1.cloud.thethings.network
    topic: v3/multicare-acerra@ttn/devices/+/up
  my-netatmo:
    provider: netatmo
    request_interval: 600
```

The `provider` value must match one of the ids in
`rime.providers.PROVIDER_REGISTRY`. Any keys whose names match the provider's
constructor parameters are forwarded automatically by `from_config`.

### `generic-http` provider config

`GenericHTTPProvider` is intended for plain JSON HTTP APIs where a lightweight
field mapping is sufficient:

- Required: `url`
- Common: `method` (`GET` default), `request_interval`, `headers`, `params`
- Decapsulation mapping:
  - `response_items_field` (if the top-level response wraps a list)
  - `sensor_id_field` (defaults to `sensor_id`)
  - `payload_field` (optional nested dict of readings)
  - `provider_timestamp_field` / `phenomenon_timestamp_field` (optional, ISO or epoch)

The CLI (`rime setup`) prefers to write this file for you and will
introspect `auth_method` to know which credential setup to invoke.

### `eltek-gprs-server` provider config

Ingests CSV files produced by **Eltek Gateway GPRS Server** (also called GPRS
Server / Gateway): an older Windows host utility that receives data pushed by
GenII receiver loggers (SRV250, SRV450, …) and writes one append-oriented
Windows CSV per logger. This provider does not speak to the logger or Gateway
over the network; it only polls the file the Gateway already wrote.

The logger id in the CSV header is the **Thing**; each mapped channel is a
**Sensor** UUID. Required keys:

- `file_path`, `iana_timezone`
- `channel_sensor_map`: vendor channel id → Sensor `name` (e.g. `Ch-005` → `K02212-12943-Ch-005`)

Quantity routing is model-tier (each channel Sensor’s ``SupportedSensors``
parser / normalizer). SensorConfig still links Datastreams for STA provisioning.

### `ott-hydra3` provider config

Ingests sectioned OTT MIS snapshots written under dated directories by **OTT
Hydras 3**. Uses `DiffDirectoryWatcher` (line-set diff of rewrite files).
`<STATION>` is the Thing; each mapped `<SENSOR>` id is a Sensor UUID.

Required keys:

- `root_dir`, `file_glob`, `iana_timezone`
- `channel_sensor_map`: Hydras sensor id → Sensor `name` (e.g. `0010` → `MULTIC_001-0010`)

## See also

- [`../transport/`](../transport/README.md) — abstract transports that
  providers extend.
- [`../transformers/decapsulators/`](../transformers/decapsulators/) —
  application envelope decapsulators.
- [`../transformers/ingest_registry.py`](../transformers/ingest_registry.py) —
  per-model deserializer/decoder/transformer wiring.
- [`../transformers/messages.py`](../transformers/messages.py) — ingress message
  types from decapsulate → decode → parse.
- [`../paths.py`](../paths.py) — `TOKENS_DIR`, `CREDENTIALS_DIR`, and
  related helpers used to locate provider credentials.

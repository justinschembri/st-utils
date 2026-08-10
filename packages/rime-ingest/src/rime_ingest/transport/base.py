"""Abstract base for sensor transports.

A `SensorTransport` is a managed engagement with an upstream data source. It
owns the threading model, the wire-message-processing pipeline, and the
exception policy. Concrete subclasses specialise on the interaction model
(poll vs. subscription) and ultimately on the provider (Netatmo, TTS, ...).

## Ingest pipeline

`_process_wire_message` drives a two-stage pipeline for every wire message received:

Provider tier (transport / provider level):

    _decode_wire          raw wire data  →  decoded form   (identity by default)
    _deserialize_wire     decoded form   →  Python object  (identity by default)
    _decapsulate_wire        →  DecapsulatedMessage

The decapsulated message carries a list of IdentifiedPayload entries — one per
logical sensor present in the wire message — together with optional
EnvelopeMetadata (timestamps and channel hints from the provider envelope).

Model tier (per IdentifiedPayload, keyed by sensor model from INGEST_COMPONENT_MAP):

    parser.parse          →  ObservationRecord (sensor_uuid + observations + timestamps)
    normalizer.from_record  →  vendor fields → SensorThings observations
    frost_observation_upload →  push to FROST

Time-series carriers (:class:`~rime.transformers.messages.IdentifiedTimeSeriesPayload`)
are expanded in ``_process_wire_message`` into one :class:`~rime.transformers.messages.IdentifiedPayload`
per sample before the model tier runs.

The application-tier hooks default to identity so transports whose libraries
already handle wire decoding (ObsPy for SeedLink, lnetatmo for Netatmo) need
not override them. MQTT overrides `_deserialize_wire` with `json.loads`.

Authentication is intentionally *not* a base-class concern — credential
storage and resolution differ enough between providers (OAuth tokens, API
keys, TLS certs, no auth at all) that pinning a shape here would force every
provider to adapt to the lowest common denominator. Providers handle their
own auth in whatever method they need.
"""
#stdlib
import inspect
import logging
import os
import queue
import threading
import traceback
from abc import ABC, abstractmethod
from typing import Any, Literal
#internal

from .buffers import BufferedObservationFlush, TransportBufferStore
from ..config import FROST_ENDPOINT_DEFAULT
from ..frost.post import frost_observation_upload
from ..monitor import netmon
from ..transformers.ingest_registry import resolve_identified_payload
from ..transformers.messages import (
    DecapsulatedMessage,
    EnvelopeMetadata,
    IdentifiedPayload,
    IdentifiedTimeSeriesPayload,
)
from ..exceptions import (
        FrostUploadFailure, 
        UnexpectedProviderMessage,
        UnpackError,
        UnregisteredSensorError
        )
from ..frost.errors import FrostRequestError

from ..transformers.types import SensorRegistry, SensorUUID, SupportedSensors

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")

#TODO: this constant should not be private, nor defined here. 
_DEFAULT_FROST_ENDPOINTS: tuple[str, ...] = tuple(
    e.strip() for e in os.getenv("FROST_ENDPOINT", FROST_ENDPOINT_DEFAULT).split(",")
)

class SensorTransport(ABC):
    """Abstract base for any managed link to an upstream sensor data source.

    Owns the worker thread, wire-message ingest pipeline, observation buffering,
    and exception policy. Subclasses specialise the interaction model (poll vs.
    subscription) and must implement :meth:`_run` and :meth:`_decapsulate_wire`.

    Attributes:
        app_name: Application identifier; also used as the worker thread name.
        max_retries: Consecutive failure budget interpreted by concrete transports.
        frost_endpoints: FROST STA endpoints set at :meth:`start`.
        sensor_registry: Map of sensor UUID to registry entry, set at :meth:`start`.
    """

    def __init__(
        self,
        app_name: str,
        *,
        max_retries: int = 1,
        buffer_store: TransportBufferStore | None = None,
    ):
        """Initialize transport state without starting the worker thread.

        Args:
            app_name: Application identifier for logging and thread naming.
            max_retries: Consecutive failure budget for concrete transports.
            buffer_store: Optional shared observation buffer store; a private
                store is created when omitted.
        """
        self.app_name = app_name
        self.max_retries = max_retries
        self._buffer_store = buffer_store or TransportBufferStore()
        self.frost_endpoints: list[str] = []
        #TODO: sensor_registry as an attr is a codesmell
        self.sensor_registry: SensorRegistry = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # dunder ###################################################################
    def __hash__(self) -> int:
        """Return a hash based on ``app_name``."""
        return hash(self.app_name)

    def __eq__(self, other) -> bool:
        """Return True when ``other`` is a transport with the same ``app_name``."""
        if not isinstance(other, SensorTransport):
            return False
        return other.app_name == self.app_name

    # construction #############################################################
    @classmethod
    def from_config(cls, app_name: str, config: dict[str, Any]) -> "SensorTransport":
        """Instantiate a transport from a YAML application config dict.

        Constructor parameters are discovered via ``inspect.signature``; config
        keys that match a parameter are forwarded. Unknown keys are ignored.

        Args:
            app_name: Application identifier passed to the constructor.
            config: Application config mapping; matching keys become kwargs.

        Returns:
            A new instance of ``cls``.
        """
        sig = inspect.signature(cls)
        kwargs: dict[str, Any] = {"app_name": app_name}
        for param_name in sig.parameters:
            if param_name in config:
                kwargs[param_name] = config[param_name]
        return cls(**kwargs)

    # lifecycle ################################################################
    def _preflight(self) -> bool:
        """Run optional checks before the worker thread starts.

        Returns:
            False to abort startup; True to continue. Default always returns True.
        """
        return True

    @property
    def is_alive(self) -> bool:
        """Whether the worker thread exists and is currently running."""
        return self._thread is not None and self._thread.is_alive()

    @abstractmethod
    def _run(self) -> None:
        """Drive data acquisition in the worker thread.

        Implemented by a direct descendant. The loop must obtain wire messages
        and pass each to :meth:`_process_wire_message`.
        """
        ...

    def start(
        self,
        sensor_registry: SensorRegistry,
        *,
        frost_endpoints: list[str] | tuple[str, ...] = _DEFAULT_FROST_ENDPOINTS,
    ) -> None:
        """Start the transport's worker thread.

        Skips startup if :meth:`_preflight` fails. Idempotent: re-calling while
        the thread is alive is a no-op.

        Args:
            sensor_registry: Map of sensor UUID to model + linked datastreams.
            frost_endpoints: FROST STA base URLs to upload observations to.
        """
        self.sensor_registry = sensor_registry
        self.frost_endpoints = list(frost_endpoints)
        if not self._preflight():
            event_logger.warning(
                f"Preflight check failed for {self.app_name}; not starting connection."
            )
            return
        if self.is_alive:
            return
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=self.app_name,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop and flush pending observation buffers."""
        self._stop_event.set()
        self._flush_sensor_buffers()

    def restart(self, join_timeout: int = 15) -> None:
        """Stop the worker thread, then start it again with the same registry.

        Args:
            join_timeout: Seconds to wait for the old thread to exit.

        Raises:
            AttributeError: If no sensor registry was set by a prior :meth:`start`.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(join_timeout)
        if not self.sensor_registry:
            raise AttributeError(
                f"Trying to restart {self.app_name} thread with no "
                "sensor registry available."
            )
        self._stop_event.clear()
        self.start(self.sensor_registry, frost_endpoints=self.frost_endpoints)

    # processing ###############################################################
    def _decode_wire(self, raw: Any) -> Any:
        """Convert raw wire data to a form suitable for deserialization.

        Default is identity. Override when the transport delivers opaque bytes
        that need a codec (e.g. base64, UTF-8) first.

        Args:
            raw: Provider-native wire payload.

        Returns:
            Decoded wire data for :meth:`_deserialize_wire`.
        """
        return raw

    def _deserialize_wire(self, decoded: Any) -> Any:
        """Parse decoded wire data into a Python object.

        Default is identity. Override for serialized formats (JSON, CBOR,
        Protobuf, ...). ``MQTTTransport`` uses ``json.loads``; SeedLink and HTTP
        leave this as identity because their libraries already return objects.

        Args:
            decoded: Output of :meth:`_decode_wire`.

        Returns:
            In-memory object for :meth:`_decapsulate_wire`.
        """
        return decoded

    @abstractmethod
    def _decapsulate_wire(self, wire_message: Any) -> DecapsulatedMessage:
        """Strip the provider envelope into identified sensor payloads.

        Implemented by a concrete provider. Receives the output of
        :meth:`_deserialize_wire` (a Python object, never raw bytes).

        Args:
            wire_message: Deserialized provider message.

        Returns:
            A :class:`~rime.transformers.messages.DecapsulatedMessage` whose
            ``identified_payloads`` list has one entry per logical sensor in
            the wire message.
        """

    def _process_wire_message(self, wire_message: Any) -> None:
        """Run the full two-stage ingest pipeline for a single wire message.

        Provider tier::

            _decode_wire → _deserialize_wire → _decapsulate_wire

        Model tier (per sample after any time-series fan-out)::

            parser.parse → normalizer.from_record → frost_observation_upload

        Args:
            wire_message: Raw provider payload as received by the transport.
        """
        decoded_wire = self._decode_wire(wire_message)
        deserialized_wire = self._deserialize_wire(decoded_wire)
        decapsulated = self._decapsulate_wire(deserialized_wire)

        for identified in decapsulated.identified_payloads:
            sensor_uuid = identified.sensor_uuid
            try:
                envelope = decapsulated.envelope_metadata
                self.run_payload_ingest(
                    resolve_identified_payload(identified, self.sensor_registry),
                    envelope,
                )
            except (UnregisteredSensorError, UnpackError, KeyError) as e:
                self._exception_handler(e, sensor_id=sensor_uuid, stage="model_ingest")
                continue

    def run_payload_ingest(
        self,
        identified: IdentifiedPayload | IdentifiedTimeSeriesPayload,
        envelope: EnvelopeMetadata | None,
    ) -> None:
        """Run model-tier ingest for one resolved identified payload.

        Optionally deserializes/decodes, expands time-series carriers into
        point-in-time samples, then parses, normalizes, buffers, and uploads.

        Args:
            identified: Registry-resolved payload with ingest components set.
            envelope: Optional provider envelope metadata (timestamps, channel).

        Raises:
            UnpackError: If the payload was not resolved before model ingest.
        """
        components = identified.components
        sensor_model = identified.sensor_model
        sensor_uuid = identified.sensor_uuid
        if components is None or sensor_model is None:
            raise UnpackError(
                RuntimeError("IdentifiedPayload must be resolved before model ingest.")
            )
        if components.deserializer:
            identified = components.deserializer.deserialize(identified, envelope) #type: ignore
        if components.decoder:
            identified = components.decoder.decode(identified, envelope) #type: ignore
        if isinstance(identified, IdentifiedTimeSeriesPayload):
            point_in_time_inputs = identified.expand_to_point_in_time(envelope)
        else:
            point_in_time_inputs = iter([(identified, envelope)])

        for sample_identified, sample_envelope in point_in_time_inputs:
            record = components.parser.parse(sample_identified, sample_envelope)
            normalizer = components.normalizer.from_record(record)
            st_observations = normalizer.to_stObservations()
            for st_obs in st_observations:
                try:
                    debug_logger.debug(f"{st_obs=} {sensor_uuid=}")
                    flush = self._buffer_store.record_observation(
                        sensor_uuid,
                        sensor_model,
                        st_obs,
                    )
                    if flush is None:
                        continue

                    try:
                        self._upload_buffered_observation(flush, sensor_model)
                    except (FrostUploadFailure, FrostRequestError) as e:
                        # Clear pending flush so later samples are not blocked.
                        self._buffer_store.commit_flush(flush.key)
                        self._exception_handler(e, sensor_id=sensor_uuid)
                except (FrostUploadFailure, FrostRequestError) as e:
                    self._exception_handler(e, sensor_id=sensor_uuid)

    def _upload_buffered_observation(
        self,
        flush: BufferedObservationFlush,
        sensor_model: SupportedSensors,
    ) -> None:
        """Upload a ready buffer flush to every configured FROST endpoint.

        Args:
            flush: Buffer snapshot ready for STA upload.
            sensor_model: Sensor model used for success logging.
        """
        for endpoint in self.frost_endpoints:
            frost_observation_upload(
                flush.sensor_uuid,
                flush.payload,
                frost_endpoint=endpoint,
            )
        self._buffer_store.commit_flush(flush.key)
        event_logger.info(
            f"Received and processed a wire message from {self.app_name} "
            f"from a {sensor_model.value} sensor."
        )
        netmon.add_named_count("push_success", f"{flush.sensor_uuid}", 1)

    def _flush_sensor_buffers(self) -> None:
        """Upload any in-flight or partial buffers for this transport's sensors."""
        for flush in self._buffer_store.drain_pending_for_sensors(self.sensor_registry):
            sensor_uuid, sensor_model, _ = flush.key
            try:
                for endpoint in self.frost_endpoints:
                    frost_observation_upload(
                        flush.sensor_uuid,
                        flush.payload,
                        frost_endpoint=endpoint,
                    )
                self._buffer_store.commit_flush(flush.key)
                event_logger.info(
                    f"Flushed buffered observations from {self.app_name} "
                    f"for a {sensor_model.value} sensor on shutdown."
                )
            except FrostUploadFailure as e:
                self._exception_handler(e, sensor_id=sensor_uuid)

    #TODO: reconsider exception handler as part of the class, should be a global concern
    def _exception_handler(self, e: Exception | None, **kwargs) -> Literal[0, 1]:
        """Classify and log an ingest exception.

        Args:
            e: Exception raised during ingest, or None.
            **kwargs: Extra fields merged into the debug context (e.g.
                ``sensor_id``, ``stage``).

        Returns:
            ``0`` for a transient/skippable failure, ``1`` for a real failure.
        """

        def _log(msg: str, debug_context: dict[str, str]):
            main_logger.error(msg)
            debug_logger.debug(debug_context)

        debug_context = {
            "application": f"{self.app_name}",
            "exception_type": f"{type(e)}",
            "exception_message": f"{e}",
            **kwargs,
        }
        name = e.__repr__()
        if isinstance(e, UnpackError):
            msg = f"{name}: failed to unpack a wire message."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, queue.Empty):
            msg = f"{name}: MQTT queue is empty."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, UnregisteredSensorError):
            msg = f"{name}: sensor is not registered."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, KeyError):
            msg = f"{name}: sensor model has no ingest components configured."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, UnexpectedProviderMessage):
            msg = f"{name}: unexpected provider message."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, FrostUploadFailure):
            msg = f"{name}: failure to upload to FROST."
            _log((f"{self.app_name} " + msg), debug_context)
            return 1
        else:
            msg = f"{e}"
            msg += traceback.format_exc()
            _log((f"{self.app_name} " + msg), debug_context)
            return 1

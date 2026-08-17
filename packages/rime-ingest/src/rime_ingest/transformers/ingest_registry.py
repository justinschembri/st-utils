"""Per-model ingest component wiring.

Each sensor model resolves an optional deserializer, an optional decoder,
a parser, and a normalizer class.

``deserializer`` and ``decoder`` default to ``None`` (skip).  Set them only
when the native payload arriving from decapsulation is not yet in a form the
parser can handle:

- ``deserializer``: opaque bytes/str → structured Python object
  (e.g. base64 frm_payload → dict via CBOR or a vendor codec)
- ``decoder``: structured values → semantic observation values
  (e.g. raw ADC register → temperature float, bit-field expansion)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Type

from rime_ingest.exceptions import UnregisteredSensorError
from rime_ingest.transformers.normalizers.dragino import DraginoLSN50v2_S31Normalizer
from rime_ingest.transformers.parsers.dragino import DraginoLSN50v2_S31Parser

from .decoders.core import Decoder
from .deserializers.core import Deserializer
from .messages import IdentifiedPayload, IdentifiedTimeSeriesPayload
from .normalizers.core import Normalizer
from .normalizers.milesight import (
    MilesightAm103lNormalizer,
    MilesightAm308lNormalizer,
)
from .decoders.kinemetrics import KinemetricsEtna2Decoder
from .normalizers.kinemetrics import KinemetricsEtna2
from .normalizers.netatmo import NetatmoNWS03
from .parsers import MilesightAm103lParser, MilesightAm308lParser, NetatmoNWS03Parser, Parser
from .parsers.kinemetrics import KinemetricsEtna2Parser
from .parsers.probes import (
    HeatFluxPlateParser,
    OttRlsParser,
    ThermocoupleKParser,
    ThermocoupleTParser,
)
from .normalizers.probes import (
    HeatFluxPlateNormalizer,
    OttRlsNormalizer,
    ThermocoupleKNormalizer,
    ThermocoupleTNormalizer,
)
from .types import SensorRegistry, SensorUUID, SupportedSensors


@dataclass(frozen=True, slots=True)
class IngestModelComponents:
    """Components of model-level ingestion pipeline."""
    parser: Type[Parser]
    normalizer: Type[Normalizer]
    deserializer: Type[Deserializer] | None = None
    decoder: Type[Decoder] | None = None

# TODO: it is possible that we have made some assumption on the decoding and 
# dserialization steps that the provider would have applied when defining both
# the functionality of parsers and the way the ingest component map is defined.
INGEST_COMPONENT_MAP: dict[SupportedSensors, IngestModelComponents] = {
    SupportedSensors.MILESIGHT_AM103L: IngestModelComponents(
        parser=MilesightAm103lParser,
        normalizer=MilesightAm103lNormalizer,
    ),
    SupportedSensors.MILESIGHT_AM308L: IngestModelComponents(
        parser=MilesightAm308lParser,
        normalizer=MilesightAm308lNormalizer,
    ),
    SupportedSensors.NETATMO_NWS03: IngestModelComponents(
        parser=NetatmoNWS03Parser,
        normalizer=NetatmoNWS03,
    ),
    SupportedSensors.KINEMETRICS_ETNA2: IngestModelComponents(
        parser=KinemetricsEtna2Parser,
        normalizer=KinemetricsEtna2,
        decoder=KinemetricsEtna2Decoder,
    ),
    SupportedSensors.DRAGINO_LSN50V2_S31: IngestModelComponents(
        parser=DraginoLSN50v2_S31Parser, 
        normalizer=DraginoLSN50v2_S31Normalizer
    ),
    SupportedSensors.HEAT_FLUX_PLATE: IngestModelComponents(
        parser=HeatFluxPlateParser,
        normalizer=HeatFluxPlateNormalizer,
    ),
    SupportedSensors.THERMOCOUPLE_T: IngestModelComponents(
        parser=ThermocoupleTParser,
        normalizer=ThermocoupleTNormalizer,
    ),
    SupportedSensors.THERMOCOUPLE_K: IngestModelComponents(
        parser=ThermocoupleKParser,
        normalizer=ThermocoupleKNormalizer,
    ),
    SupportedSensors.OTT_RLS: IngestModelComponents(
        parser=OttRlsParser,
        normalizer=OttRlsNormalizer,
    ),
}


def _lookup_ingest_components(
    sensor_uuid: SensorUUID,
    sensor_registry: SensorRegistry,
) -> tuple[SupportedSensors, IngestModelComponents]:
    entry = sensor_registry.get(sensor_uuid)
    if entry is None:
        raise UnregisteredSensorError
    return entry.model, INGEST_COMPONENT_MAP[entry.model]


def resolve_identified_payload(
    identified: IdentifiedPayload | IdentifiedTimeSeriesPayload,
    sensor_registry: SensorRegistry,
) -> IdentifiedPayload | IdentifiedTimeSeriesPayload:
    """Attach ``sensor_model`` and ``components`` from deployment + code registries."""
    sensor_model, components = _lookup_ingest_components(
        identified.sensor_uuid, sensor_registry
    )
    return replace(identified, sensor_model=sensor_model, components=components)


def resolve_time_series_payload(
    identified: IdentifiedTimeSeriesPayload,
    sensor_registry: SensorRegistry,
) -> IdentifiedTimeSeriesPayload:
    """Attach ``sensor_model`` and ``components`` for a time-series carrier."""
    sensor_model, components = _lookup_ingest_components(
        identified.sensor_uuid, sensor_registry
    )
    return replace(identified, sensor_model=sensor_model, components=components)

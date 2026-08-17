"""Canonical data-types involved in various transformations."""

# standard
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ThingUUID = str
SensorUUID = str

# CanonicalDatastreams should somehow be extended to declare what resultType 
# it accepts (in line with STA v2)
class CanonicalDatastreams(Enum):
    """
    Enumerations for various canonical datastream names. It is imperative that
    datastream names passed in the ingest application match the names of Datastream
    entity in the FROST server. Thus:
    
    - This enum should be called by a `Normalizer` sublcass when applying the
    `.to_stObservation` method. 

    - The initial set-up which creates a FROST entity from a `SensorConfig` only
    allows datastream names which are part of this enum.

    Names identify the *quantity* (heat flux, temperature), not the instrument.
    Instrument identity lives on the Sensor entity / SupportedSensors model.
    """
    PHENOMENON_TIME = "phenomenon_time"
    BATTERY_LEVEL = "battery_level"
    BATTERY_VOLTAGE = "battery_voltage"
    HUMIDITY_INDOOR = "humidity"
    AIR_HUMIDITY = "humidity_air"
    CO2_INDOOR = "co2"
    TEMP_IN = "temperature_indoor"
    AIR_TEMPERATURE = "temperature_air"
    TEMPERATURE = "temperature"
    LIGHT_LVL_IN = "light_level"
    PIR = "passive_infrared"
    PM10 = "particulate_matter_10"
    PM_2PT5 = "particulate_matter_2_5"
    G_PRESSURE_IN = "gauge_pressure"
    A_PRESSURE_IN = "absolute_pressure"
    NOISE_IN = "noise"
    TVOC = "total_volatile_organic_compounds"
    HNE = "HNE"
    HNN = "HNN"
    HNZ = "HNZ"
    HEAT_FLUX = "heat_flux"
    WATER_LEVEL = "water_level"

class SupportedSensors(Enum):
    MILESIGHT_AM103L = "milesight.am103l"
    MILESIGHT_AM308L = "milesight.am308l"
    NETATMO_NWS03 = "netatmo.nws03"
    KINEMETRICS_ETNA2 = "kinemetrics.etna2"
    DRAGINO_LSN50V2_S31 = "dragino.lsn50v2-s31"
    # Probe instruments (e.g. on a multi-channel logger Thing)
    HEAT_FLUX_PLATE = "heat_flux.plate"
    THERMOCOUPLE_T = "thermocouple.t"
    THERMOCOUPLE_K = "thermocouple.k"
    OTT_RLS = "ott.rls"


@dataclass(frozen=True, slots=True)
class SensorRegistryEntry:
    """Runtime registry row for one STA Sensor from a SensorConfig file.

    ``datastreams`` are the canonical Datastream ``name`` values linked to this
    Sensor in config (quantity identity for envelope / upload routing).
    """

    model: SupportedSensors
    datastreams: tuple[CanonicalDatastreams, ...]


SensorRegistry = dict[SensorUUID, SensorRegistryEntry]


class SupportedProviders(Enum):
    NETATMO = "netatmo"
    THE_THINGS_NETWORK = "ttn"
    RIME_HTTP = "rime-http"
    ELTEK_GPRS_SERVER = "eltek-gprs-server"
    OTT_HYDRA3 = "ott-hydra3"

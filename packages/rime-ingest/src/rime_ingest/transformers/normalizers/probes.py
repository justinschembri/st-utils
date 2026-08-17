"""STA normalizers for single-quantity probe instruments."""

from .core import Normalizer
from ..types import CanonicalDatastreams


class HeatFluxPlateNormalizer(Normalizer):
    heat_flux: float | None = None

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "heat_flux": CanonicalDatastreams.HEAT_FLUX,
    }


class ThermocoupleTNormalizer(Normalizer):
    temperature: float | None = None

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "temperature": CanonicalDatastreams.TEMPERATURE,
    }


class ThermocoupleKNormalizer(Normalizer):
    temperature: float | None = None

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "temperature": CanonicalDatastreams.TEMPERATURE,
    }


class OttRlsNormalizer(Normalizer):
    water_level: float | None = None

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "water_level": CanonicalDatastreams.WATER_LEVEL,
    }

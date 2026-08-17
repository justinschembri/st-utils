"""Top-level normalizer registry.

Maps supported sensor models to their observation normalizer implementation.
"""

from typing import Type


from .normalizers.core import Normalizer
from .normalizers import milesight, netatmo, kinemetrics, dragino, probes
from .types import SupportedSensors

#TODO: is this mapping relevant at all?
NORMALIZER_MAP: dict[SupportedSensors, Type[Normalizer]] = {
    SupportedSensors.MILESIGHT_AM103L: milesight.MilesightAm103lNormalizer,
    SupportedSensors.MILESIGHT_AM308L: milesight.MilesightAm308lNormalizer,
    SupportedSensors.NETATMO_NWS03: netatmo.NetatmoNWS03,
    SupportedSensors.KINEMETRICS_ETNA2: kinemetrics.KinemetricsEtna2,
    SupportedSensors.DRAGINO_LSN50V2_S31: dragino.DraginoLSN50v2_S31Normalizer,
    SupportedSensors.HEAT_FLUX_PLATE: probes.HeatFluxPlateNormalizer,
    SupportedSensors.THERMOCOUPLE_T: probes.ThermocoupleTNormalizer,
    SupportedSensors.THERMOCOUPLE_K: probes.ThermocoupleKNormalizer,
    SupportedSensors.OTT_RLS: probes.OttRlsNormalizer,
}

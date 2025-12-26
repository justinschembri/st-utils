"""All the transformer maps live here."""
#standard
from typing import Type
#internal
from .types import SupportedSensors
from .core import NativePayloadTransformer
from . import milesight
from . import netatmo

TRANSFORMER_MAP: dict[SupportedSensors, Type[NativePayloadTransformer]]= {
        SupportedSensors.MILESIGHT_AM103L: milesight.MilesightAm103lPayload,
        SupportedSensors.MILESIGHT_AM308L: milesight.MilesightAm308lPayload,
        SupportedSensors.NETATMO_NWS03: netatmo.NetatmoNWS03,
        }


"""Concrete sensor application providers."""

from .eltek import EltekGPRSServerProvider
from .netatmo import NetatmoProvider
from .ott_hydras3 import OTTHydra3Provider
from .registry import PROVIDER_REGISTRY
from .rime_http import RimeServerHttpProvider
from .tts import TTSProvider

__all__ = [
    "EltekGPRSServerProvider",
    "OTTHydra3Provider",
    "NetatmoProvider",
    "TTSProvider",
    "RimeServerHttpProvider",
    "PROVIDER_REGISTRY",
]

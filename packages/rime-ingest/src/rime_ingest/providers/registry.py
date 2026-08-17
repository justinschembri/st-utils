"""Provider registry keyed by config-facing provider ids."""

from rime_ingest.providers.gen_seedlink import GenericSeedLinkProvider
from .eltek import EltekGPRSServerProvider
from .netatmo import NetatmoProvider
from .ott_hydras3 import OTTHydra3Provider
from .rime_http import RimeServerHttpProvider
from .tts import TTSProvider

PROVIDER_REGISTRY = {
    "netatmo": NetatmoProvider,
    "tts": TTSProvider,
    "rime-http": RimeServerHttpProvider,
    "generic-seedlink": GenericSeedLinkProvider,
    "eltek-gprs-server": EltekGPRSServerProvider,
    "ott-hydra3": OTTHydra3Provider,
}


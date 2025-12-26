# standard
import logging
from typing import Callable
# external
# internal
from .types import ObservedProperties
from .core import NativePayloadTransformer
# environment setup
logger = logging.getLogger(__name__)


class MilesightAm103lPayload(NativePayloadTransformer):

    battery: int
    co2: float
    humidity: float
    temperature: float

    NAME_TRANSFORM: dict[str, ObservedProperties]= {
        "battery": ObservedProperties.BATTERY_LEVEL,
        "co2": ObservedProperties.CO2_INDOOR,
        "humidity": ObservedProperties.HUMIDITY_INDOOR,
        "temperature": ObservedProperties.TEMP_IN,
    }
    
    TRANSFORM: dict[str, Callable] = {}


class MilesightAm308lPayload(NativePayloadTransformer):

    battery: int
    co2: float
    humidity: float
    light_level: int
    pir: str 
    pm10: int
    pm2_5: int
    pressure: float
    temperature: float
    tvoc: float

    NAME_TRANSFORM: dict[str, ObservedProperties] = {
        "battery": ObservedProperties.BATTERY_LEVEL,
        "co2": ObservedProperties.CO2_INDOOR,
        "humidity": ObservedProperties.HUMIDITY_INDOOR,
        "light_level": ObservedProperties.LIGHT_LVL_IN,
        "pir": ObservedProperties.PIR,
        "pm10": ObservedProperties.PM10,
        "pm2_5": ObservedProperties.PM_2PT5,
        "pressure": ObservedProperties.G_PRESSURE_IN,
        "temperature": ObservedProperties.TEMP_IN,
        "tvoc": ObservedProperties.TVOC,
    }

    TRANSFORM: dict[str, Callable]= {
            "pir": lambda x: True if x=="trigger" else False,
            }


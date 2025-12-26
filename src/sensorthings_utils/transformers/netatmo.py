"""
FROST server support for Netatmo Sensor NWS03.
A sample of the unpacked data:
{
    "70:ee:50:7f:9d:32":
    {
        "time_utc": 1765374089,
        "Temperature": 23.3,
        "CO2": 871,
        "Humidity": 46,
        "Noise": 33,
        "Pressure": 1014.8,
        "temp_trend": "stable",
        "pressure_trend": "up",
    },
{
    "70:ee:50:7f:a4:76":
    {...}
}

"""

# standard
from datetime import datetime
from typing import Callable
# internal
from .core import NativePayloadTransformer
from .types import ObservedProperties


class NetatmoNWS03(NativePayloadTransformer):

    time_utc: int
    temperature: float
    co2: int
    humidity: int
    noise: int
    pressure: float

    TRANSFORM: dict[str, Callable] = {
            "time_utc": lambda x: datetime.fromtimestamp(x) 
            }

    NAME_TRANSFORM: dict[str, ObservedProperties] = {
        "time_utc": ObservedProperties.PHENOMENON_TIME,
        "temperature": ObservedProperties.TEMP_IN,
        "co2": ObservedProperties.CO2_INDOOR,
        "humidity": ObservedProperties.HUMIDITY_INDOOR,
        "noise": ObservedProperties.NOISE_IN,
        "pressure": ObservedProperties.G_PRESSURE_IN,
    }


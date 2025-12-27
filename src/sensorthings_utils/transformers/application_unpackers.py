"""
Unpack a decoded payload from an aplication's native format into a sensors
native format.
"""

# standard
import logging
from enum import Enum
from typing import Any, Type
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

# external
# internal
from .types import SensorID
from ..exceptions import MissingPayloadKeysError, UnpackError

# environment set-up
# loggers
main_logger = logging.getLogger("main")
debug_logger = logging.getLogger("debug")
event_logger = logging.getLogger("events")


class SupportedConnections(str, Enum):
    NETATMO = "netatmo"
    TTS = "TheThingsStack"


# TODO: phenomenon time might be something transmitted by application and not by
# the sensor.
@dataclass
class NativePayload:
    """
    A successfully unpacked uplink message from an application.

    An unpacked is considered 'native' when all metadata added by the applicat-
    -ion not required by the ST model has been removed. A native payload may
    include more than one set of observations.
    """

    data: dict[SensorID, dict[str, Any]]
    application_timestamp: datetime | None

    def __bool__(self) -> bool:
        """A successful unpack is truthy."""
        return True

    def items(self):
        return self.data.items()

    @property
    def sensor_ids(self):
        return self.data.keys()


class ApplicationUnpacker(ABC):
    """Baseclass for application unpacking."""

    application_timestamp: bool

    @staticmethod
    @abstractmethod
    def unpack(
        app_payload: Any,
    ) -> NativePayload:
        """Public unpack interface."""
        ...


# UNPACKER DEFINITIONS #########################################################
class NullUnpacker(ApplicationUnpacker):
    """Null class for applicationless systems."""

    @staticmethod
    def unpack(app_payload: Any):
        return app_payload


class NetatmoUnpacker(ApplicationUnpacker):
    application_timestamp = False
    """
    As of Dec 2025, the netatmo API (as wrapped by the `lnetatmo` module)
    returns a list[dict] object:

    [
        {
            "_id": "70:ee:50:7f:9d:32",
            "station_name": "Room120 (Indoor)",
            "reachable": True,
            "wifi_status": 74,
            "dashboard_data": {
                "time_utc": 1765374089,
                "Temperature": 23.3,
                "CO2": 871,
                "Humidity": 46,
                "Noise": 33,
                "Pressure": 1014.8,
                "temp_trend": "stable",
                "pressure_trend": "up",
            },
            "modules": [
                {
                    "_id": "02:00:00:7f:a8:cc",
                    "module_name": "Outdoor",
                    "battery_percent": 100,
                }
            ],
        },
        {
            "_id": "70:ee:50:7f:a4:76",
            ...
        },
    ]
    """

    @staticmethod
    def unpack(app_payload: list[dict[str, Any]]) -> NativePayload:
        unpacked_payload = {}
        try:
            for device in app_payload:
                if not device["reachable"]:
                    continue
                unpacked_payload[device["_id"]] = device["dashboard_data"]
            return NativePayload(data=unpacked_payload, application_timestamp=None)
        except KeyError as e:
            raise MissingPayloadKeysError(e)
        except Exception as e:
            raise UnpackError(e)


class TTSUnpacker(ApplicationUnpacker):
    """Sample TTS payload:
    {
            "end_device_ids": {
                ...
                "dev_eui": "24E124707D378803",
                ...
            },
            ...
            "uplink_message": {
                ...
                "decoded_payload": {
                    "battery": 53,
                    "co2": 4665,
                    "humidity": 75.5,
                    "light_level": 1,
                    "pir": "idle",
                    "pm10": 107,
                    "pm2_5": 101,
                    "pressure": 1017.5,
                    "temperature": 23.1,
                    "tvoc": 1,
                },
                "rx_metadata": [
                    {
                        ...
                        },
                        "time": "2025-12-25T20:08:00.920247Z",
                        ...
                        "received_at": "2025-12-25T20:08:00.937463873Z",
                    }
                ],
                "settings": {
                    ...
                        }
                    },
                    "frequency": "867500000",
                    "timestamp": 2193199502,
                    "time": "2025-12-25T20:08:00.920247Z",
                },
                "received_at": "2025-12-25T20:08:00.975695414Z",
                "consumed_airtime": "0.097536s",
                "version_ids": {
                    "brand_id": "milesight-iot",
                    "model_id": "am308l",
                    "hardware_version": "1.x",
                    "firmware_version": "1.x",
                    "band_id": "EU_863_870",
                },
                "network_ids": {
                        ...
                },
                "last_battery_percentage": {
                        ...
                },
            },
        }
    """

    application_timestamp = True

    @staticmethod
    def unpack(app_payload: dict[str, Any]) -> NativePayload:
        unpacked_payload = {}
        try:
            sensor_id = app_payload["end_device_ids"]["dev_eui"]
            payload = {**app_payload["uplink_message"]["decoded_payload"]}
            unpacked_payload[sensor_id] = payload
            app_timestamp = app_payload["uplink_message"]["rx_metadata"][0][
                "received_at"
            ]
        except KeyError as e:
            raise MissingPayloadKeysError(e)

        return NativePayload(data=unpacked_payload, application_timestamp=app_timestamp)


APP_UNPACKERS: dict[str | None, Type[ApplicationUnpacker]] = {
    None: NullUnpacker,
    "netatmo": NetatmoUnpacker,
    "tts": TTSUnpacker,
}

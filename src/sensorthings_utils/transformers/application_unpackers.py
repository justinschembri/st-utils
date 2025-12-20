"""
Unpack a decoded payload from an aplication's native format into a sensors 
native format.
"""
#standard
import logging
from enum import Enum
from typing import Any, Type
from abc import ABC, abstractmethod
#external
#internal
from .types import SuccessfulUnpack
#environment set-up
#loggers
main_logger = logging.getLogger("main")
debug_logger = logging.getLogger("debug")
event_logger = logging.getLogger("events")
#exceptions
class UnpackError(Exception):
    """Parent exception for sensor uplink message unpack failures."""

class MissingPayloadKeysError(UnpackError):
    """Failed to unpack the uplink message due to missing keys."""

class UnregisteredSensorError(Exception):
    """Receieved a message from an unregistered sensor."""

class SupportedConnections(str, Enum):
    NETATMO = "netatmo"
    TTS = "TheThingsStack"

class ApplicationUnpacker(ABC):

    @staticmethod
    @abstractmethod
    def unpack(
               app_payload: Any, 
               ) ->  SuccessfulUnpack:
        """Public unpack interface."""
        ...

# UNPACKER DEFINITIONS #########################################################
class NullUnpacker(ApplicationUnpacker):
    """Null class for applicationless systems."""

    @staticmethod
    def unpack(app_payload: Any):
        return app_payload

class NetatmoUnpacker(ApplicationUnpacker):
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
    def unpack(app_payload: list[dict[str, Any]]):

        unpacked_payload = {}
        try:
            for device in app_payload:
                if not device["reachable"]:
                    continue
                unpacked_payload[device["_id"]] = device["dashboard_data"]
            return SuccessfulUnpack(unpacked_payload=unpacked_payload)
        # logging handled upstream
        except KeyError as e:
            raise MissingPayloadKeysError(e)
        except Exception as e:
            raise UnpackError(e)



class TTSUnpacker(ApplicationUnpacker):

    @staticmethod
    def unpack(app_payload: dict[str, Any]) -> SuccessfulUnpack:
        unpacked_payload = {}
        try: 
            unpacked_payload[app_payload["end_device_ids"]["dev_eui"]] ={
                **app_payload["uplink_message"]["decoded_payload"],
                "phenomenon_time": app_payload["uplink_message"]["rx_metadata"][0]["received_at"],
            }
        except KeyError as e:
            raise MissingPayloadKeysError(e)

        return SuccessfulUnpack(unpacked_payload=unpacked_payload)

APP_UNPACKERS: dict[str | None, Type[ApplicationUnpacker]] = {
    None: NullUnpacker,
    "netatmo": NetatmoUnpacker,
    "tts": TTSUnpacker
}


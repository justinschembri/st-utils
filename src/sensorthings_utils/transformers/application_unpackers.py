"""
Unpack a decoded payload from an aplication's native format into a sensors 
native format.
"""
#standard
#external
#internal
import logging
from enum import Enum
from typing import Any, Type, Union
from abc import ABC, abstractmethod

from sensorthings_utils.connections import NetatmoConnection, SensorApplicationConnection, TTSConnection
from .types import FailedUnpack, SuccessfulUnpack
#environment set-up
#loggers
main_logger = logging.getLogger("main")
debug_logger = logging.getLogger("debug")
event_logger = logging.getLogger("events")


class SupportedConnections(str, Enum):
    NETATMO = "netatmo"
    TTS = "TheThingsStack"

class ApplicationUnpacker(ABC):

    @staticmethod
    def _warn(app_payload: Any, app_name:str, e:Exception):
        """Generic warning to raise during failed unpacks."""
        main_logger.warning(
                f"Unable to unpack payload {app_payload} for "
                f"{app_name}: {type(e).__name__}: {e}"
                )
    
    @staticmethod
    @abstractmethod
    def unpack(
               app_payload: Any, 
               app_name: str | None
               ) ->  SuccessfulUnpack | FailedUnpack:
        """Public unpack interface."""
        ...

# UNPACKER DEFINITIONS #########################################################
class NullUnpacker(ApplicationUnpacker):
    """Null class for applicationless systems."""

    @staticmethod
    def unpack(app_payload: Any, app_name: str):
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
    def unpack(app_payload: list[dict[str, Any]], app_name: str):

        unpacked_payload = {}
        try:
            for device in app_payload:
                unpacked_payload[device["_id"]] = device["dashboard_data"]
            return SuccessfulUnpack(unpacked_payload=unpacked_payload)
        except Exception as e:
            ApplicationUnpacker._warn(app_payload, app_name, e)
            return FailedUnpack(application_payload=app_payload)


class TTSUnpacker(ApplicationUnpacker):

    @staticmethod
    def unpack(app_payload):
        unpacked_payload: dict[str, Any] | FailedUnpack = {}

        uplink_message = self.application_payload["uplink_message"]
        if "decoded_payload" not in uplink_message:
            main_logger.info(
                    "Skipped payload with no uplink message for "
                    f"{self.application_name}."
                    )
            return FailedUnpack(application_payload=self.application_payload)
        try: 
            unpacked_payload[self.application_payload["end_device_ids"]["dev_eui"]] ={
                **self.application_payload["uplink_message"]["decoded_payload"],
                "phenomenon_time": self.application_payload["uplink_message"]["rx_metadata"][0]["received_at"],
            }

        except Exception as e:
            self._warn(e)
            return FailedUnpack()

        return unpacked_payload

APP_UNPACKERS: dict[
        Union[Type[SensorApplicationConnection], None], 
        Type[ApplicationUnpacker]
        ] = {
    None: NullUnpacker,
    NetatmoConnection: NetatmoUnpacker,
    TTSConnection: TTSUnpacker
}


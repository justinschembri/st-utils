# standard
from typing import List, Literal
import time
import logging

# external

# internal
from sensorthings_utils.config import SENSOR_CONFIG_FILES
from sensorthings_utils import netatmo
from sensorthings_utils.sensor_things.extensions import (
    SensorArrangementMap,
    SensorArrangement,
)
from sensorthings_utils.netatmo import initial_setup

SupportedSensors = Literal[
    "all",
    "netatmo",
]


def stream_all(sensor_types: List[SupportedSensors]) -> None:
    logging.info("Sensor Stream starting (sleep.)")
    time.sleep(30)
    for f in SENSOR_CONFIG_FILES:
        sensor_arrangement_map = SensorArrangementMap(f)
        sensor_arrangement = SensorArrangement(sensor_arrangement_map)
        initial_setup(sensor_arrangement)
    while True:
        ALL = True if "all" in sensor_types else False
        if "netatmo" in sensor_types or ALL:
            netatmo.stream()


if __name__ == "__main__":
    stream_all(["all"])

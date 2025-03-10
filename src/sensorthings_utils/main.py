# standard
from typing import List, Literal
# external

# internal
from sensorthings_utils import netatmo

SupportedSensors = Literal[
    "all",
    "netatmo",
]


def stream_all(sensor_types: List[SupportedSensors]) -> None:
    ALL = True if "all" in sensor_types else False
    if "netatmo" in sensor_types or ALL:
        netatmo.stream()


if __name__ == "__main__":
    while True:
        print("Application being called!")
        # stream_all()

# standard
from typing import List, Literal
# external

# internal
from sensorthings_utils import netatmo

SupportedSensors = Literal["netatmo",]


def stream_all(sensor_types: List[SupportedSensors]) -> None:
    if "netatmo" in sensor_types:
        netatmo.stream()


if __name__ == "__main__":
    while True:
        print("Application being called!")
        # stream_all()

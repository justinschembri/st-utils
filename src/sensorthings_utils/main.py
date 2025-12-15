# standard
from typing import List, Optional
import logging
from pathlib import Path
import importlib
import yaml
import time
import threading
import os

# internal
from sensorthings_utils import config  # noqa: F401
from sensorthings_utils.config import (
    APPLICATION_CONFIG_FILE,
    SENSOR_CONFIG_FILES,
    FROST_ENDPOINT_DEFAULT,
)
from sensorthings_utils.sensor_things.extensions import (
    SensorConfig,
    SensorArrangement,
)
import sensorthings_utils.frost as frost
from sensorthings_utils.connections import SensorApplicationConnection
from sensorthings_utils.monitor import network_monitor

# import from config.py:
main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")


def parse_application_config(config_path: Path) -> set[SensorApplicationConnection]:
    """
    Parse YAML config and return set of connection objects.

    Args:
        config_path: Path to the YAML application configuration file

    Returns:
        Set of connection instances.
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    connections = set()
    connections_module = importlib.import_module("sensorthings_utils.connections")

    for app_name, app_config in config["applications"].items():
        class_name = app_config["connection_class"]

        try:
            # if you're wondering what this does: the connections module 
            # (of type `ModuleType`) object
            # includes its classes and functions as attrs.
            ConnectionClass = getattr(connections_module, class_name)
        except AttributeError:
            raise ValueError(
                f"Connection class '{class_name}' not found in "
                "sensorthings_utils.connections"
            )

        if not issubclass(ConnectionClass, SensorApplicationConnection):
            raise ValueError(
                f"{class_name} is not a valid SensorApplicationConnection subclass"
            )
        connections.add(ConnectionClass.from_config(app_name, app_config))

    debug_logger.debug(f"{connections=}")
    return connections


def _setup_sensor_arrangements(
    exclude: Optional[List[str]],
    sensor_config_paths: List[Path] = SENSOR_CONFIG_FILES,
):
    """
    An initial set up of the sensor arrangement based on the configuration files.
    """
    for f in sensor_config_paths:
        if exclude and f.name in exclude:
            continue
        sensor_config = SensorConfig(f)
        if not sensor_config.is_valid:
            network_monitor.add_count("sensor_config_fail", 1)
            main_logger.warning(f"{f} is an invalid sensor configuration file!")
            main_logger.warning(
                f"Skipping {f}, data from this sensor is not being processed."
            )
            continue
        sensor_arrangement = SensorArrangement(sensor_config)
        network_monitor.expected_sensors.add(sensor_arrangement.id)
        frost.initial_setup(sensor_arrangement)


def push_available(
    exclude: Optional[List[str]] = None,
    frost_endpoint: Optional[str] = None,
    start_delay: int = 30,
) -> None:
    """
    Push available sensor connections.

    :param exclude: Sensor's (MAC addresses) to exclude form the stream,
        defaults to None.
    :type exclude: List[str] | None
    :param frost_endpoint: Endpointt to push to, defaults to FROST_ENDPOINT
        set up in src/config.py (usually localhost)
    :type frost_endpoint: str | None
    """
    frost_endpoint = (
        frost_endpoint or os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    )
    os.environ["FROST_ENDPOINT"] = frost_endpoint
    # TODO: frost_endpoint run in containers is pointing to container reference
    event_logger.info(
        f"Sensor stream starts in {start_delay}s, target: {frost_endpoint}."
    )
    time.sleep(start_delay)
    # generate a list of connections
    sensor_connections = parse_application_config(APPLICATION_CONFIG_FILE)

    network_monitor.set_starting_threads(
        [_.application_name for _ in sensor_connections]
    )

    for connection in sensor_connections:
        connection.start_pull_transform_push_thread()

    event_logger.info(
        f"Started {threading.active_count()-1} application threads: "
        + f"{set([i.name for i in threading.enumerate()][1:])}"
    )

    try:
        while True:
            # TODO: network_monitor should write to a metrics file for eventual
            # integration with monitoring tools.
            network_monitor.report()
    except KeyboardInterrupt:
        for conn in sensor_connections:
            event_logger.info(f"Stopping thread for {conn.application_name}")
            conn.stop_pull_transform_push_thread()

    event_logger.info("Successfully shutdown connections.")


if __name__ == "__main__":
    push_available()

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
from sensorthings_utils.loggers import setup_loggers  # noqa: F401
from sensorthings_utils.paths import APPLICATION_CONFIG_FILE
from sensorthings_utils.config import (
    generate_sensor_config_files,
    FROST_ENDPOINT_DEFAULT,
)
from sensorthings_utils.sensor_things.extensions import (
    SensorConfig,
    SensorArrangement,
)
import sensorthings_utils.frost as frost
from sensorthings_utils.connections import SensorApplicationConnection
from sensorthings_utils.monitor import netmon
from sensorthings_utils.transformers.types import SensorID, SupportedSensors

# import from config.py:
setup_loggers()
main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")

def parse_application_config(config_path: Path) -> set[SensorApplicationConnection]:
    """
    Parse application YAML config and return set of connection objects.

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

    return connections


def _setup_sensor_arrangements(sensor_config: SensorConfig) -> None:
    """
    Turns a SensorConfig file into database entities on the FROST server.

    Args
        sensor_config (SensorConfig)

    Returns
        None. POSTS entities to the FROST database instance.
    """
    if not sensor_config.is_valid:
        netmon.add_count("sensor_config_fail", 1)
        main_logger.warning(
            f"{sensor_config._filepath} is an invalid sensor configuration " "file."
        )
        return None

    sensor_arrangement = SensorArrangement(sensor_config)
    frost.initial_setup(sensor_arrangement)


def push_available(
    sensor_config_paths: List[Path] = generate_sensor_config_files(),
    exclude: Optional[List[SensorID]] = None,
    frost_endpoint: Optional[str] = None,
    start_delay: int = 30,
) -> None:
    """
    Start app threads and begin collecting data, pushing to FROST server.

    Args
        - sensor_config_path: a list sensor configuration files.
        - exclude: sensors to exclude.
        - frost_endpoint: HTTP FROST endpoint to push too.
        - start_delay: a delay before starting the loop.
    Raises
        - None.
    """
    os.environ["FROST_ENDPOINT"] = (
        frost_endpoint or os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    )
    # TODO: frost_endpoint run in containers is pointing to container reference
    event_logger.info(
        f"Sensor stream starts in {start_delay}s, target: "
        f"{os.getenv('FROST_ENDPOINT')}."
    )
    time.sleep(start_delay)
    # INITIAL SETUP ############################################################
    sensor_registry: dict[SensorID, SupportedSensors] = {}
    for f in sensor_config_paths:
        if exclude and f.name in exclude:
            continue
        sensor_config = SensorConfig(f)
        sensor_registry[sensor_config.name] = SupportedSensors(sensor_config.model)
        netmon.expected_sensors.add(sensor_config.name)
        _setup_sensor_arrangements(sensor_config)
    # generate a list of connections
    sensor_connections = parse_application_config(APPLICATION_CONFIG_FILE)

    netmon.set_starting_threads([_.app_name for _ in sensor_connections])

    for connection in sensor_connections:
        connection.start_pull_transform_push_thread(sensor_registry)

    event_logger.info(
        f"Started {threading.active_count()-1} application threads: "
        + f"{set([i.name for i in threading.enumerate()][1:])}"
    )

    try:
        while True:
            # TODO: network_monitor should write to a metrics file for eventual
            # integration with monitoring tools.
            netmon.report(interval=30)
    except KeyboardInterrupt:
        for conn in sensor_connections:
            if conn._thread and conn._thread.is_alive():
                event_logger.info(f"Stopping thread for {conn.app_name}")
                conn.stop_pull_transform_push_thread()
                conn._thread.join(5)

    event_logger.info("Successfully shutdown connections.")
    return None


if __name__ == "__main__":
    push_available()

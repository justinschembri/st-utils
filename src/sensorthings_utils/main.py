# standard
from typing import List, Optional
import time
from datetime import datetime
import threading
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path
# external

# internal
from sensorthings_utils.config import (
        SENSOR_CONFIG_FILES,
        FROST_ENDPOINT_DEFAULT,
        ROOT_DIR
        )
from sensorthings_utils.sensor_things.extensions import (
    SensorConfig,
    SensorArrangement,
)
import sensorthings_utils.frost as frost
from sensorthings_utils.connections import (
    CredentialedHTTPSensorConnection,
    CredentialedMQTTSensorConnection,
    NetatmoConnection,
    TTSConnection,
)
from sensorthings_utils.monitor import network_monitor

# Root Logger ------------------------------------------------------------------
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Debug Logger -----------------------------------------------------------------
debug_logger = logging.getLogger("debug")
debug_logger.setLevel(logging.DEBUG)
# Network Monitor Logger -------------------------------------------------------
network_monitor_logger = logging.getLogger("network_monitor")
network_monitor_logger.setLevel(logging.INFO)
# Main Logger ------------------------------------------------------------------
main_logger = logging.getLogger(__name__)
main_logger.setLevel(logging.INFO)
# Warning Logger ---------------------------------------------------------------
warning_logger = logging.getLogger("warnings")
warning_logger.setLevel(logging.WARNING)
# File Handler (general)--------------------------------------------------------
general_logfile_name = "general.log"
logfile = Path(ROOT_DIR / ("logs/" + general_logfile_name))
logfile.parent.mkdir(exist_ok=True)
file_handler = TimedRotatingFileHandler(
    filename=logfile, when="midnight", interval=1, backupCount=30, encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s [%(name)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(file_formatter)
# File Handler (debug)----------------------------------------------------------
debug_logfile_name = "debug.log"
logfile = Path(ROOT_DIR / ("logs/" + debug_logfile_name))
logfile.parent.mkdir(exist_ok=True)
debug_handler = logging.FileHandler(filename=logfile)
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter(
    "%(asctime)s [%(name)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
debug_handler.setFormatter(debug_formatter)
# Console Handlers -------------------------------------------------------------
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    "%(asctime)s [%(name)s:%(lineno)d]: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(console_formatter)
# Attach Handlers --------------------------------------------------------------
root_logger.addHandler(file_handler)
debug_logger.addHandler(debug_handler)
network_monitor_logger.addHandler(console_handler)
main_logger.addHandler(console_handler)


def push_available(
    exclude: Optional[List[str]] = None, frost_endpoint: Optional[str] = None
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
    exclude = exclude or []
    frost_endpoint = (
        frost_endpoint or os.getenv("FROST_ENDPOINT") or FROST_ENDPOINT_DEFAULT
    )
    os.environ["FROST_ENDPOINT"] = frost_endpoint
    main_logger.info(f"Sensor stream starts in 30s, target: {frost_endpoint}")
    time.sleep(30)
    sensor_connections: set[
        CredentialedHTTPSensorConnection | CredentialedMQTTSensorConnection
    ] = set()
    if not SENSOR_CONFIG_FILES:
        raise ValueError(f"No sensor configurations passed.")
    for f in SENSOR_CONFIG_FILES:
        if f.name in exclude:
            continue
        sensor_config = SensorConfig(f)
        if not sensor_config.is_valid:
            network_monitor.add_count("sensor_config_fail", 1)
            root_logger.error(f"{f} is an invalid sensor configuration file!")
            root_logger.error(
                f"Skipping {f}, data from this sensor is not being processed."
            )
            continue
        sensor_arrangement = SensorArrangement(sensor_config)
        network_monitor.expected_sensors.add(sensor_arrangement.id)
        application_name = sensor_arrangement.application_name
        host = sensor_arrangement.host
        frost.initial_setup(sensor_arrangement)
        match host:
            case "netatmo":
                sensor_connections.add(NetatmoConnection(application_name))
            case _ if host.endswith(".thethings.network"):
                sensor_connections.add(
                    TTSConnection(
                        application_name=application_name,
                        mqtt_host=host,
                    )
                )
    network_monitor.set_starting_threads(
        [_.application_name for _ in sensor_connections]
    )
    for connection in set(sensor_connections):
        connection.start(push=True)

    main_logger.info(
        f"Started {threading.active_count()-1} application threads: "
        + f"{set([i.name for i in threading.enumerate()][1:])}"
    )

    try:
        while True:
            network_monitor.report()
    except KeyboardInterrupt:
        for conn in sensor_connections:
            main_logger.info(f"Stopping thread for {conn.application_name}")
            conn.stop()

    logging.info("Successfully shutdown connections.")


if __name__ == "__main__":
    push_available()

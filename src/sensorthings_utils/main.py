# standard
from typing import List, Optional
import logging
import time
import threading
import os
# internal
from sensorthings_utils import config # noqa: F401 
from sensorthings_utils.config import (
        SENSOR_CONFIG_FILES,
        FROST_ENDPOINT_DEFAULT,
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

main_logger = logging.getLogger("main")
root_logger = logging.getLogger("root")
debug_logger = logging.getLogger("debug")

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
    #TODO: frost_endpoint run in containers is pointing to container reference
    main_logger.info(f"Sensor stream starts in 30s, target: {frost_endpoint}")
    time.sleep(30)
    sensor_connections: set[
        CredentialedHTTPSensorConnection | CredentialedMQTTSensorConnection
    ] = set()
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

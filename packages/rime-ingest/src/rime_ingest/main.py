# standard
from copy import deepcopy
from typing import List, Optional
import logging
from pathlib import Path
import yaml
import time
import threading
import os

# internal
from rime_ingest.loggers import setup_loggers  # noqa: F401
from rime_ingest.paths import APPLICATION_CONFIG_FILE
from rime_ingest.config import (
    FROST_ENDPOINT_DEFAULT,
    generate_sensor_config_files,
    get_frost_auth_header,
)
from rime_ingest.providers.registry import PROVIDER_REGISTRY
from rime_ingest.sta.extensions import SensorConfig
from rime_ingest.frost.orchestrators import initial_setup
from rime_ingest.frost.sanitization import sanitize_frost_endpoint
from rime_ingest.transport import SensorTransport
from rime_ingest.monitor import netmon
from rime_ingest.transformers.types import SensorRegistry, SensorUUID


# import from config.py:
setup_loggers()
main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")

def parse_application_config(config_path: Path) -> set[SensorTransport]:
    """
    Parse application YAML config and return set of transport instances.

    Args:
        config_path: Path to the YAML application configuration file

    Returns:
        Set of transport instances.
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    connections = set()

    for app_name, app_config in config["applications"].items():
        provider_name = app_config.get("provider", "").strip().lower()
        if not provider_name:
            raise ValueError(
                f"Application '{app_name}' is missing required key 'provider'."
            )

        ProviderClass = PROVIDER_REGISTRY.get(provider_name)
        if ProviderClass is None:
            valid = ", ".join(sorted(PROVIDER_REGISTRY))
            raise ValueError(
                f"Unknown provider '{provider_name}' for application '{app_name}'. "
                f"Valid providers: {valid}"
            )

        if not issubclass(ProviderClass, SensorTransport):
            raise ValueError(
                f"{ProviderClass.__name__} is not a valid SensorTransport subclass"
            )
        connections.add(ProviderClass.from_config(app_name, app_config))

    return connections

def _setup_sensor_arrangements(
    sensor_config: SensorConfig,
    endpoint: str,
) -> None:
    """Provision a SensorConfig as FROST entities (idempotent).

    Args:
        sensor_config: Parsed sensor configuration.
        endpoint: FROST endpoint URL from ``FROST_ENDPOINT``, e.g.
            ``http://host/FROST-Server`` or ``http://host/FROST-Server/v1.1``.
    """
    if not sensor_config.is_valid:
        netmon.add_count("sensor_config_fail", 1)
        main_logger.warning(
            f"{sensor_config._filepath} is an invalid sensor configuration file."
        )
        return None

    endpoint, root_url, version = sanitize_frost_endpoint(endpoint)

    initial_setup(
        sensor_config,
        root_url=root_url,
        version=version,
        write_auth_headers=get_frost_auth_header("write", endpoint),
        read_auth_headers=get_frost_auth_header("read", endpoint),
    )

def push_available(
    sensor_config_paths: Optional[List[Path]] = None,
    exclude: Optional[List[SensorUUID]] = None,
    frost_endpoints: Optional[str] = None,
    start_delay: int = 10,
) -> None:
    """Start app threads and begin collecting data, pushing to FROST server.

    Args:
        sensor_config_paths: List of sensor configuration file paths.
            Resolved from ``SENSOR_CONFIG_PATH`` when omitted.
        exclude: Sensor UUIDs to skip.
        frost_endpoints (str): One or more FROST endpoints to push too, defaults to
            ``FROST_ENDPOINT`` env or FROST_ENDPOINT_DEFAULT.
        start_delay: Seconds to wait before starting the collection loop.
    """
    if sensor_config_paths is None:
        sensor_config_paths = generate_sensor_config_files()
    if frost_endpoints is None:
        frost_endpoints = os.getenv("FROST_ENDPOINT", FROST_ENDPOINT_DEFAULT)
    endpoints = [e.strip() for e in frost_endpoints.split(",")]
    event_logger.info(
        f"Streaming starting in {start_delay}s, pushing to {len(endpoints)} target/s: {endpoints}."
    )
    time.sleep(start_delay)
    # INITIAL SETUP ############################################################
    sensor_registry: SensorRegistry = {}
    for f in sensor_config_paths:
        if exclude and f.name in exclude:
            continue
        sensor_config = SensorConfig(f)
        for uuid, entry in sensor_config.sensors.items():
            sensor_registry[uuid] = entry
            netmon.expected_sensors.add(uuid)
        for endpoint in endpoints:
            _setup_sensor_arrangements(deepcopy(sensor_config), endpoint)
    # generate a list of connections
    sensor_connections = parse_application_config(APPLICATION_CONFIG_FILE)

    netmon.set_starting_threads([_.app_name for _ in sensor_connections])

    for connection in sensor_connections:
        connection.start(sensor_registry, frost_endpoints=endpoints)
        # network monitor will be responsible for restarting dead threads:
        netmon.connections.add(connection)

    event_logger.info(
        f"Started {threading.active_count()-1} application threads: "
        + f"{set([i.name for i in threading.enumerate()][1:])}"
    )

    try:
        while True:
            # TODO: network_monitor should write to a metrics file for eventual
            # integration with monitoring tools.
            netmon.report(interval=5)
    except KeyboardInterrupt:
        for conn in sensor_connections:
            if conn.is_alive:
                event_logger.info(f"Stopping thread for {conn.app_name}")
                conn.stop()
                if conn._thread is not None:
                    conn._thread.join(5)

    event_logger.info("Successfully shutdown connections.")
    return None


if __name__ == "__main__":
    push_available()

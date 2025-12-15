# standard
import os
from typing import Dict, List, Any
import logging

# external
# internal
from ..frost import make_frost_object, find_datastream_url
from ..sensor_things.core import Observation
from ..monitor import network_monitor

# environment setup
CONTAINER_ENVIRONMENT = True if os.getenv("CONTAINER_ENVIRONMENT") else False
logger = logging.getLogger(__name__)

# consntants
EXPECTED_KEYS = ["sensor_name", "phenomenon_time", "observations"]


def _filter(payload: Dict, exclude: List[str] | None = None) -> Dict[str, Any]:
    """
    Return parsed Milesight payload, keeping only relevant SensorThings data.

    Returns a dict with keys: `sensor_name`, `phenomenon_time`,
    `observations`.

    """
    data = {}
    try:
        data["sensor_name"] = payload["end_device_ids"]["dev_eui"]
        if exclude and data["sensor_name"] in exclude:
            return {}
        data["phenomenon_time"] = payload["uplink_message"]["rx_metadata"][0][
            "received_at"
        ]
        data["observations"] = payload["uplink_message"]["decoded_payload"]
    except KeyError as e:
        logger.debug(f"{payload=}")
        logger.critical(f"Milesight AM103L payload is invalid: missing key: {e}")
        return {}
    return data


def _transform(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return transformed observations.

    :param data: Raw data from Milesight sensor.
    :type data:
    :return:
    :rtype:
    """
    ...
    MILESIGHT_TO_DATASTREAM_MAP = {
        "battery": "battery_level",
        "co2": "co2",
        "humidity": "humidity",
        "temperature": "temperature_indoor",
    }

    for key in EXPECTED_KEYS:
        if key not in data:
            raise KeyError(f"Missing key {key}.")

    transformed_observations = {
        transformed_key: data["observations"][key]
        for key, transformed_key in MILESIGHT_TO_DATASTREAM_MAP.items()
    }
    transformed_data = {}
    transformed_data["observations"] = transformed_observations
    for metadata in ["sensor_name", "phenomenon_time"]:
        transformed_data[metadata] = data[metadata]
    return transformed_data


def frost_upload(
    raw_payload: Dict[str, Any],
    *,
    exclude: List[str] = [""],
    application_name: str | None = None,
) -> None:
    """Filter, transform and push Milesight AM103L package to the FROST server."""

    try:
        transformed_payload = _transform(_filter(raw_payload, exclude))
    except KeyError:
        logger.warning(
            f"Malformed or empty AM103L payload: {raw_payload=}. "
            + "Nothing was pushed to FROST."
        )
        return None

    sensor_name = transformed_payload["sensor_name"]
    phenomenon_time = transformed_payload["phenomenon_time"]
    observations = transformed_payload["observations"]  # type: Dict[str, Any]
    for datastream_name, result in observations.items():
        upload_success = False
        push_link = find_datastream_url(
            sensor_name, datastream_name, CONTAINER_ENVIRONMENT
        )
        observation = Observation(
            result=result,
            phenomenonTime=phenomenon_time,
        )
        if not push_link:
            logger.critical(
                "Unable to upload payload: no datastream URL found. "
                + f"Details: {sensor_name=}, {datastream_name=}"
            )
        try:
            make_frost_object(observation, push_link, application_name)
            upload_success = True
        except Exception as e:
            logger.critical(
                f"Failure adding observation/s for {sensor_name}. Has the datastream been set up? Error: {e}"
            )
        if not upload_success:
            application_name = application_name or ""
            network_monitor.add_named_count("push_fail", application_name, 1)
    return None

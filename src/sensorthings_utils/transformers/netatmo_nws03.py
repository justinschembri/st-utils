"""
FROST server support for Netatmo Sensor NWS03.
A sample of the unpacked data:
{
    "70:ee:50:7f:9d:32":
    {
        "time_utc": 1765374089,
        "Temperature": 23.3,
        "CO2": 871,
        "Humidity": 46,
        "Noise": 33,
        "Pressure": 1014.8,
        "temp_trend": "stable",
        "pressure_trend": "up",
    },
{
    "70:ee:50:7f:a4:76":
    {...}
}

"""

# standard
import logging
from typing import List, Dict, Any, Generator, Tuple

# internal
from ..sensor_things.core import Observation
from ..config import CONTAINER_ENVIRONMENT
from sensorthings_utils.frost import make_frost_object, find_datastream_url
from ..monitor import netmon

logger = logging.getLogger(__name__)


def _validation_filter(
    payload: Dict[str, Any]],
    exclude: List[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Validate and filter a native dict object from a Netatmo NWS03 sensor.

    Args:
        `payload` ([Dict[str, Any]])
    """
    data = {}
    if not payload[0]:
        logger.warning("No netatmo data returned.")
    if exclude:
        payload = [i for i in payload if i["_id"] not in exclude]
    for item in payload:
        if item["reachable"] == False:
            logger.warning(f"Netatmo Station {item["_id"]} is unreachable.")
            return data
        station_id = item["_id"]
        dashboard_data = item["dashboard_data"]
        dashboard_data["station_id"] = station_id
        data[station_id] = dashboard_data
    return data


# TODO: #7 Consider creating a standard namedTuple for returns.
def _transform(data: Dict[str, Any]) -> Generator[Tuple[Any, ...]]:
    """
    Transform data from a station into an standardized format.
    """
    NETATMO_TO_DATASTREAM_MAP = {
        "Temperature": "temperature_indoor",
        "CO2": "co2",
        "Humidity": "humidity",
        "Noise": "noise",
        "Pressure": "gauge_pressure",
        "AbsolutePressure": "absolute_pressure",
    }
    sensor_name = data["station_id"]
    result_time = data["time_utc"]  # type: ignore
    for observation_type, result_value in data.items():
        # there are a number of values in a response we're not interested in.
        if observation_type not in NETATMO_TO_DATASTREAM_MAP:
            continue
        datastream_name = NETATMO_TO_DATASTREAM_MAP[observation_type]
        yield (sensor_name, datastream_name, result_time, result_value)  # type: ignore


def frost_upload(
    payload: List[Dict[str, Any]],
    *,
    exclude: List[str] | None = None,
    application_name: str | None = None,
) -> None:
    """Extract, transform and load Netatmo devices linked to your account."""
    for station in _validation_filter(payload, exclude).values():
        observation_stream = _transform(station)
        for o in observation_stream:
            upload_success = False
            sensor_name = o[0]
            datastream_name = o[1]
            phenomenon_time = o[2]
            result = o[3]
            push_link = find_datastream_url(
                sensor_name, datastream_name, CONTAINER_ENVIRONMENT
            )
            if not push_link:
                logger.warning(
                    "Unable to upload payload: no datastream URL found. "
                    + f"Details: {sensor_name=}, {datastream_name=}"
                )
                continue
            observation = Observation(
                result=result,
                phenomenonTime=phenomenon_time,
            )
            try:
                make_frost_object(observation, push_link, application_name)
                upload_success = True
            except Exception as e:
                logger.warning(
                    f"Failure adding observation/s for {sensor_name}. Has the datastream been set up? Error: {e}"
                )
            if not upload_success:
                application_name = application_name or ""
                netmon.add_named_count("push_fail", application_name, 1)
    return None

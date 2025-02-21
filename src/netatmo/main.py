# standard
import urllib.request as request
from urllib import error
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Generator, Tuple, Literal, TYPE_CHECKING

# external
import lnetatmo as ln

# internal

if TYPE_CHECKING:
    from .sensor_things.core import Thing, SensorThingsObject

BASE_URL = "http://localhost:8080/FROST-Server.HTTP-2.3.1/v1.1/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("netatmo")

AUTHENTICATION = ln.ClientAuth()
NETATMO_TO_DATASTREAM_MAP = {
    "Temperature": "temperature_indoor",
    "C02": "co2",
    "Humidity": "humidity",
    "Noise": "noise",
    "Pressure": "pressure",
    "AbsolutePressure": "absolute_pressure",
}


def _retrieve_latest_observations(
    station_ids: List[str] | None = None,
) -> Dict[str, Dict[str, str | int | float]]:
    """
    Return latest observations from all Netatmo weather stations.

    :param station_ids: Description
    :type station_ids:
    :return: Description
    :rtype: Dict[str, Dict[str, str | int | float]]
    """
    data = {}  # type: Dict[str, Dict[str, str | int | float]]
    weather_stations = station_ids or ln.WeatherStationData(AUTHENTICATION).stations
    for station in weather_stations:
        station_data = weather_stations[station]["dashboard_data"]  # type: ignore
        station_data["station_id"] = weather_stations[station]["_id"]  # type: ignore
        data[station] = station_data
    logger.info(f"Retrieved {len(data)} sets of observations.")
    return data


def _generate_query_params(data: Dict[str, str | int | float]) -> Generator[Tuple[Any]]:
    sensor_name = data["station_id"]
    result_time = datetime.fromtimestamp(data["time_utc"])  # type: ignore
    for observation_type, result_value in data.items():
        # there are a number of values in a response we're not interested in.
        if observation_type not in NETATMO_TO_DATASTREAM_MAP:
            continue
        datastream_name = NETATMO_TO_DATASTREAM_MAP[observation_type]
        yield (sensor_name, datastream_name, result_time, result_value)  # type: ignore


def make_frost_object(entity: "SensorThingsObject") -> Dict[str, str]:
    """
    Add a Frost Object to the FROST Server and return URLs to linked objects.

    :param station_ids: entity
    :type station_ids: SensorThingsObject
    :return: URL of linked Objects
    :rtype: Dict[str]

    """
    expected_links_map = {
        "Sensor": ("Datastreams",),
        "Datastream": ("ObservedProperties", "Observations", "Sensors", "Things"),
        "ObservedProperty": ("Datastreams",),
        "Thing": ("Datastreams", "HistoricalLocations", "Locations"),
        "Observation": ("Datastreams", "FeaturesOfInterest"),
        "FeatureOfInterest": ("Observations",),
        "HistoricalLocation": ("Things", "Locations"),
        "Location": ("HistoricalLocations", "Things"),
    }
    entity_type = entity.__class__.__name__
    expected_links = expected_links_map[entity_type]
    make_request = request.Request(
        url=BASE_URL
        + entity_type
        + "s",  # e.g. http://localhost:8080/FROST-Server.HTTP-2.3.1/v1.1/Things
        data=entity.model_dump_json(exclude={"iot_links", "id"}).encode("UTF-8"),
        method="POST",
    )
    print(entity.model_dump_json(exclude={"iot_links", "id"}).encode("UTF-8"))
    try:
        with request.urlopen(make_request) as response:
            new_object_url = response.getheader(
                "Location"
            )  # "Location" does not refer to a SensorThings Location
            logger.info(f"New {entity_type} created at {new_object_url}")
    except error.HTTPError as e:
        print(f"{e.read()}")
    with request.urlopen(new_object_url) as response:
        response = json.loads(response.read())
    return {
        str.lower(link_name + "_url"): response[link_name + "@iot.navigationLink"]
        for link_name in expected_links
    }


def netatmo_stream(sleep_time: int) -> None:
    """Placeholder function."""
    for data in _retrieve_latest_observations().values():
        observation_stream = _generate_query_params(data)
        for o in observation_stream:
            print(o)  # query / construct end point / push
        time.sleep(sleep_time)

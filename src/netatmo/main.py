# standard
import urllib.request as request
from urllib.parse import quote
from urllib import error
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Generator, Tuple, Literal, TYPE_CHECKING
import re

# external
import lnetatmo as ln

# internal

if TYPE_CHECKING:
    from .sensor_things.core import SensorThingsObject, Datastream
    from .sensor_things.extensions import SensorArrangement

BASE_URL = "http://localhost:8080/FROST-Server.HTTP-2.3.1/v1.1"

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


def make_frost_object(
    entity: "SensorThingsObject", iot_url: str | None = None
) -> Dict[str, str]:
    """
    Add a Frost Object to the FROST Server and return URLs to linked objects.

    :param entity: The SensorThing object to add to the database.
    :type entity: SensorThingsObject
    :param iot-url: URL endpoint to push to.
    :type iot-url: Optional[str].
    :return: URL of linked Objects
    :rtype: Dict[str]

    """
    expected_links_map: Dict[str, Tuple[str, ...]] = {
        "Sensor": ("Datastreams",),
        "Datastream": ("ObservedProperties", "Observations", "Sensors", "Things"),
        "ObservedProperty": ("Datastreams",),
        "Thing": ("Datastreams", "HistoricalLocations", "Locations"),
        "Observation": ("Datastreams", "FeaturesOfInterest"),
        "FeatureOfInterest": ("Observations",),
        "HistoricalLocation": ("Things", "Locations"),
        "Location": ("HistoricalLocations", "Things"),
    }
    entity_endpoints: Dict[str, str] = {
        "Sensor": "/Sensors",
        "Datastream": "/Datastreams",
        "ObservedProperty": "/ObservedProperties",
        "Thing": "/Things",
        "Observation": "/Observations",
        "FeatureOfInterest": "/FeaturesOfInterest",
        "HistoricalLocation": "/HistoricalLocations",
        "Location": "/Locations",
    }
    entity_type = entity.__class__.__name__
    expected_links = expected_links_map[entity_type]
    url = iot_url or (BASE_URL + entity_endpoints[entity_type])
    make_request = request.Request(
        url=url,
        data=entity.model_dump_json(exclude={"iot_links", "id"}).encode("UTF-8"),
        method="POST",
    )
    try:
        with request.urlopen(make_request) as response:
            new_object_url = response.getheader(
                "Location"
            )  # "Location" does not refer to a SensorThings Location
            logger.info(f"New {entity_type} created at {new_object_url}")
    except error.HTTPError as e:
        logger.critical(f"{e} {e.read()}")
        return {}
    with request.urlopen(new_object_url) as response:
        response = json.loads(response.read())

    iot_links = {
        str.lower(link_name + "_url"): response[link_name + "@iot.navigationLink"]
        for link_name in expected_links
    }
    iot_links.update({"self_url": new_object_url})
    return iot_links


def make_frost_datastream(
    entity: "Datastream", sensor_id: int, thing_id: int, observed_property_id: int
) -> None:
    url = BASE_URL + "/Datastreams"
    data = entity.model_dump(exclude={"iot_links", "id"})
    links = {
        "Thing": {"@iot.id": thing_id},
        "Sensor": {"@iot.id": sensor_id},
        "ObservedProperty": {"@iot.id": observed_property_id},
    }
    data.update(links)
    data = json.dumps(data).encode()
    make_request = request.Request(url=url, data=data, method="POST")
    try:
        with request.urlopen(make_request) as response:
            new_object_url = response.getheader(
                "Location"
            )  # "Location" does not refer to a SensorThings Location
            logger.info(f"New Datastream created at {new_object_url}")
    except error.HTTPError as e:
        logger.critical(f"{e} {e.read()}")


def filter_query(entity: str, filter_string: str) -> Dict[str, str]:
    query_url = BASE_URL + f"/{entity}?$filter=" + quote(filter_string)
    make_request = request.Request(url=query_url, method="GET")
    try:
        with request.urlopen(make_request) as response:
            response = json.loads(response.read())
            return response
    except error.HTTPError as e:
        logger.critical(f"{e} {e.read()}")
        return {}


def initial_setup(sensor_arrangement: "SensorArrangement") -> None:
    """Initial set up of a Sensor Arrangement."""

    # def _parse_iot_url(iot_url: str) -> int:
    #     """
    #     Parse IoT Url and return ID.

    #     ID is embedded in URL which has a format of ".../<EntityType>(n)"
    #     """
    #     pat = r"\((\d+)\)"
    #     id = re.search(pat, iot_url)
    #     if id:
    #         return int(id.group(1))
    #     else:
    #         raise ValueError(f"Unable to find id in url: {iot_url}")
    # Firstly, make all Things and their associated Locations
    for thing in sensor_arrangement.get_entities("Thing"):
        make_thing = make_frost_object(thing)
        iot_url = make_thing["locations_url"]
        # lookup linked locations of the thing and make them:
        for loc in thing.iot_links["locations"]:
            # pass URL of newly generated Thing's Locations to the maker:
            make_frost_object(loc, iot_url)
    # Make Sensors, which are associated only with Datastreams, which are linked later
    for sen in sensor_arrangement.get_entities("Sensor"):
        make_frost_object(sen)
    # Make ObservedProperties, also linked later with a Datastream
    for op in sensor_arrangement.get_entities("ObservedProperty"):
        make_frost_object(op)
    # Make Datastreams, linked with a one Sensor, one ObservedProperty and one Thing
    for ds in sensor_arrangement.get_entities("Datastream"):
        # Lookup the names's of the relevant Sensor, ObservedProperty and Thing:
        sen_name = ds.iot_links["sensors"][0].name  # only 1 object in list
        oprop_name = ds.iot_links["observed_properties"][0].name
        thing_name = ds.iot_links["things"][0].name
        # Query server and lookup ids:
        sen_id = filter_query("Sensors", f"name eq '{sen_name}'")["value"][0]["@iot.id"]
        oprop_id = filter_query("ObservedProperties", f"name eq '{oprop_name}'")[
            "value"
        ][0]["@iot.id"]
        thing_id = filter_query("Things", f"name eq '{thing_name}'")["value"][0][
            "@iot.id"
        ]
        make_frost_datastream(
            ds,
            sensor_id=int(sen_id),
            thing_id=int(thing_id),
            observed_property_id=int(oprop_id),
        )


def netatmo_stream(sleep_time: int) -> None:
    """Placeholder function."""
    for data in _retrieve_latest_observations().values():
        observation_stream = _generate_query_params(data)
        for o in observation_stream:
            print(o)  # query / construct end point / push
        time.sleep(sleep_time)

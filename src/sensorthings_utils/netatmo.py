"""FROST server support for Netatmo Sensor NWS03."""

# standard
import urllib.request as request
from urllib.parse import quote
from urllib import error
import json
import logging
import time
from typing import List, Dict, Any, Generator, Tuple, TYPE_CHECKING
import os

# external
import lnetatmo as ln
import dotenv
from .config import ENV_FILE

# internal
from .sensor_things.core import Observation

# type checking only
if TYPE_CHECKING:
    from .sensor_things.core import SensorThingsObject, Datastream
    from .sensor_things.extensions import SensorArrangement

# environment setup
dotenv.load_dotenv(ENV_FILE)
FROST_ENDPOINT = os.getenv("FROST_ENDPOINT")
AUTHENTICATION = ln.ClientAuth()

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("netatmo")

# common definitions

ENTITY_ENDPOINTS: Dict[str, str] = {
    "Sensor": "/Sensors",
    "Datastream": "/Datastreams",
    "ObservedProperty": "/ObservedProperties",
    "Thing": "/Things",
    "Observation": "/Observations",
    "FeatureOfInterest": "/FeaturesOfInterest",
    "HistoricalLocation": "/HistoricalLocations",
    "Location": "/Locations",
}


def _extract(
    station_ids: List[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
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


# TODO: #7 Consider creating a standard namedTuple for returns.
def _transform(data: Dict[str, Any]) -> Generator[Tuple[Any, ...]]:
    NETATMO_TO_DATASTREAM_MAP = {
        "Temperature": "temperature_indoor",
        "CO2": "co2",
        "Humidity": "humidity",
        "Noise": "noise",
        "Pressure": "pressure",
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


def check_existing_object(entity: "SensorThingsObject") -> bool:
    """
    Check if an existing SensorThingsObject already exists.
    """
    match entity.st_type:
        case (
            "Sensor"
            | "Thing"
            | "ObservedProperty"
            | "Locations"
        ):  # TODO: #5 Sort out references, sometimes plural, sometimes singular.
            if filter_query(
                entity=ENTITY_ENDPOINTS[entity.st_type],
                filter_string=f"name eq '{entity.name}'",
                url=None,
            )["value"]:
                return True
        case "Datastream":
            response = filter_query(
                entity="/Datastreams",
                filter_string=f"name eq '{entity.name}'",
                url=None,
            )
            r_objects = response["value"]
            if r_objects:
                sensor_url = r_objects[0]["Sensor@iot.navigationLink"]
                sensor_request = request.Request(url=sensor_url, method="GET")
                with request.urlopen(sensor_request) as response:
                    response = json.loads(response.read())
                    response = response["name"]
                    if response == entity.iot_links["sensors"][0].name:
                        return True
    return False


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
    if check_existing_object(entity):
        logging.info(f"Creation Skipped: object {entity.st_type} already exists.")
        return {}
    expected_links_map: Dict[str, Tuple[str, ...]] = {
        "Sensor": ("Datastreams",),
        "Datastream": ("ObservedProperties", "Observations", "Sensors", "Things"),
        "ObservedProperty": ("Datastreams",),
        "Thing": ("Datastreams", "HistoricalLocations", "Locations"),
        "Observation": ("Datastream", "FeatureOfInterest"),
        "FeatureOfInterest": ("Observations",),
        "HistoricalLocation": ("Things", "Locations"),
        "Location": ("HistoricalLocations", "Things"),
    }
    expected_links = expected_links_map[entity.st_type]
    url = iot_url or (FROST_ENDPOINT + ENTITY_ENDPOINTS[entity.st_type])
    make_request = request.Request(
        url=url,
        data=entity.model_dump_json(exclude={"iot_links", "id", "st_type"}).encode(
            "UTF-8"
        ),
        method="POST",
    )
    try:
        with request.urlopen(make_request) as response:
            new_object_url = response.getheader(
                "Location"
            )  # "Location" does not refer to a SensorThings Location
            logger.info(f"New {entity.st_type} created at {new_object_url}")
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
    if check_existing_object(entity):
        logging.info(f"Creation Skipped: object {entity.st_type} already exists.")
        return None
    url = FROST_ENDPOINT + "/Datastreams"
    data = entity.model_dump(exclude={"iot_links", "id", "st_type"})
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


def filter_query(
    filter_string: str, entity: str | None, url: str | None
) -> Dict[str, str]:
    if not url:
        query_url = FROST_ENDPOINT + f"{entity}?$filter=" + quote(filter_string)
    else:
        query_url = url + "?$filter=" + quote(filter_string)
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

    for thing in sensor_arrangement.get_entities("Thing"):
        make_thing = make_frost_object(thing)
        if not make_thing:
            break
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
        oprop_name = ds.iot_links["observedProperties"][0].name
        thing_name = ds.iot_links["things"][0].name
        # Query server and lookup ids:
        sen_id = filter_query(
            entity="/Sensors", filter_string=f"name eq '{sen_name}'", url=None
        )["value"][0]["@iot.id"]  # type: ignore
        oprop_id = filter_query(
            entity="/ObservedProperties",
            filter_string=f"name eq '{oprop_name}'",
            url=None,
        )["value"][0]["@iot.id"]  # type: ignore
        thing_id = filter_query(
            entity="/Things", filter_string=f"name eq '{thing_name}'", url=None
        )["value"][0]["@iot.id"]  # type: ignore
        make_frost_datastream(
            ds,
            sensor_id=int(sen_id),
            thing_id=int(thing_id),
            observed_property_id=int(oprop_id),
        )


def stream(sleep_time: int = 240) -> None:
    """Placeholder function."""
    for data in _extract().values():
        observation_stream = _transform(data)
        for o in observation_stream:
            sensor_name = o[0]
            datastream_name = o[1]
            phenomenon_time = o[2]
            result = o[3]

            sensor_datastreams = filter_query(
                entity="/Sensors", filter_string=f"name eq '{sensor_name}'", url=None
            )
            sensor_datastreams = sensor_datastreams["value"][0][
                "Datastreams@iot.navigationLink"
            ]  # url of datastreams #type: ignore

            datastream = filter_query(
                entity=None,
                filter_string=f"name eq '{datastream_name}'",
                url=sensor_datastreams,
            )  # type: ignore

            push_link = datastream["value"][0]["Observations@iot.navigationLink"]
            observation = Observation(
                result=result,
                phenomenonTime=phenomenon_time,
            )
            observation = make_frost_object(observation, push_link)
    time.sleep(sleep_time)
